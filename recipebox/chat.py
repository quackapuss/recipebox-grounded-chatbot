"""Explicit session state and a bounded, inspectable natural-language router."""
import copy
import json
import re
from dataclasses import dataclass, field
from .normalize import canonical, violations, contains
from .matching import match
from .substitute import adapt

NUMBERS = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
def number(text):
    return NUMBERS.get(text.lower(), int(text) if text.isdigit() else 5)


@dataclass
class State:
    query: str = ""
    include: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    max_steps: int | None = None
    pantry: list = field(default_factory=list)
    preference: str = "fewest_missing"
    mode: str = "search"
    last_ids: list = field(default_factory=list)
    selected_id: str | None = None

    def filters(self):
        return {"query":self.query, "include":self.include[:], "exclude":self.exclude[:], "max_steps":self.max_steps}


HELP = """Ask, for example:
  Find a penne pasta recipe.
  I cannot have dairy.
  How many recipes contain both garlic and onion?
  Among recipes containing tomato, which five have the fewest instruction steps?
  I have eggs, onions, tomatoes, and rice. No peanuts. At most six steps.
  Exclude eggs too.
  Show the first recipe.
  Does this recipe contain garlic?
  How many ingredients does this recipe have?
  Replace cream in this recipe without dairy.

Exact commands (recommended for unsupported wording):
  /search banana bread       New dish search; restrictions remain
  /include tomato,garlic     Add ingredient family filters
  /exclude dairy,peanut      Add hard ingredient-text restrictions
  /allow egg                 Remove that restriction explicitly
  /maxsteps 6                Set maximum counted steps (/maxsteps off removes it)
  /match 2 eggs,1 cup rice    New pantry search; restrictions remain
  /prefer fewest_missing    Or use_most / fewest_steps
  /stats count              Or average / median / common / fewest_steps / most_steps
  /show 1                   Result number or full stable recipe ID
  /adapt 1 ; remove=egg      Adapt result number or ID from local evidence
  /scope                    Display active state
  /reset                    Clear the whole session
  /json {"action":"stats","metric":"count","query":"","include":["garlic","onion"]}
  /help                     This help
  /quit                     Exit
"""


def split_items(text):
    return [x.strip(" .?") for x in re.split(r",|\band\b", text) if x.strip(" .?")]


def parse(text, state):
    """No model-generated SQL. Unsupported inputs request explicit commands."""
    low = text.lower().strip()
    if low.startswith("/json "):
        return json.loads(text[6:])
    if low.startswith("/"):
        cmd, _, arg = text.partition(" ")
        cmd, arg = cmd.lower(), arg.strip()
        if cmd in {"/help", "/scope", "/reset", "/quit"}:
            return {"action": cmd[1:]}
        if cmd == "/search": return {"action":"search", "query":arg, "include":[], "pantry":[]}
        if cmd == "/include": return {"action":"refine", "add_include":split_items(arg)}
        if cmd == "/exclude": return {"action":"refine", "add_exclude":split_items(arg)}
        if cmd == "/allow": return {"action":"refine", "allow":split_items(arg)}
        if cmd == "/maxsteps": return {"action":"refine", "max_steps":None if arg=="off" else int(arg)}
        if cmd == "/match": return {"action":"match", "query":"", "include":[], "pantry":split_items(arg)}
        if cmd == "/prefer": return {"action":"refine", "preference":arg}
        if cmd == "/stats": return {"action":"stats", "metric":arg or "count"}
        if cmd == "/show": return {"action":"show", "reference":arg or "1"}
        if cmd == "/adapt":
            reference, _, remove = arg.partition(";")
            return {"action":"adapt", "reference":reference.strip() or "1", "target":remove.strip().removeprefix("remove=")}
        return {"action":"unknown"}
    if low in {"help", "hello", "hi"}: return {"action":"help"}
    if low in {"reset", "start over", "clear all restrictions"}: return {"action":"reset"}
    if re.search(r"\b(calories|nutrition|protein content|cooking time|cook time|how long|healthiest|safest)\b", low):
        return {"action":"unavailable"}
    plan = {}
    exclusions = []
    for m in re.finditer(r"(?:cannot have|can't have|without|exclude|allergic to|no)\s+([a-z][a-z ,]*?)(?=\.|;|\?|\band\s+(?:at|prefer|with)|\btoo\b|$)", low):
        exclusions += split_items(m[1])
    if "dairy-free" in low or "dairy free" in low: exclusions.append("dairy")
    if "egg-free" in low or "egg free" in low: exclusions.append("egg")
    if exclusions: plan["add_exclude"] = exclusions
    m = re.search(r"(?:at most|maximum|max)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:instruction\s+)?steps?", low)
    if m: plan["max_steps"] = number(m[1])
    m = re.search(r"(?:suggest|show|which|top)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", low)
    if m: plan["limit"] = number(m[1])
    if "fewest additional" in low or "fewest missing" in low: plan["preference"] = "fewest_missing"
    elif "as many" in low: plan["preference"] = "use_most"
    elif "prefer fewer steps" in low: plan["preference"] = "fewest_steps"
    m = re.search(r"\breplace\s+(.+?)\s+(?:in|with)\b", low) or re.search(r"\bremove\s+([a-z ]+?)(?=\.|\?|\bfrom\b|\buse\b|$)", low)
    if m:
        return dict(plan, action="adapt", target=m[1].strip(), reference="selected")
    m = re.search(r"\bi have\s+(.+?)(?=\.|;|\bsuggest\b|\bwith no\b|\bno\b|\bat most\b|$)", low)
    if m:
        return dict(plan, action="match", query="", include=[], pantry=split_items(m[1]))
    m = re.search(r"\bdoes\s+(?:this recipe|that recipe|it|the first recipe)\s+(?:contain|have|use)\s+(.+?)[?.]?$", low)
    if m:
        return dict(plan, action="fact", attribute="ingredient", target=m[1].rstrip("?."), reference="selected")
    m = re.search(r"\bhow much\s+(.+?)\s+(?:does|is|in)\b", low)
    if m:
        return dict(plan, action="fact", attribute="ingredient", target=m[1], reference="selected")
    if any(x in low for x in ("this recipe", "that recipe", " it ", " it?")) and "how many" in low:
        if "ingredients" in low: return dict(plan, action="fact", attribute="ingredient_count", reference="selected")
        if "steps" in low: return dict(plan, action="fact", attribute="step_count", reference="selected")
    is_stat = any(p in low for p in ("how many", "percentage", "average", "median", "common ingredients", "fewest instruction steps", "fewest steps", "most steps", "most instruction steps"))
    if is_stat:
        metric = "count"
        for phrase, value in [("average","average"),("median","median"),("common ingredients","common"),("fewest","fewest_steps"),("most steps","most_steps"),("most instruction steps","most_steps")]:
            if phrase in low: metric=value
        m = re.search(r"(?:contain(?:ing)?|with)\s+(?:both\s+)?(.+?)(?=,|\?|\.|\bwhich\b|\bwhat\b|$)", low)
        if m:
            plan.update(include=split_items(m[1]), query="", pantry=[])
        elif not any(p in low for p in ("those", "these", "that", "them", "of the results")):
            plan.update(query="", include=[], pantry=[])
        return dict(plan, action="stats", metric=metric)
    if re.search(r"\b(show|ingredients|instructions|how do i make|what does it use)\b", low) and any(p in low for p in ("first", "second", "third", "this", "that", " it", "ingredients", "instructions")):
        ref = "2" if "second" in low else "3" if "third" in low else "selected"
        return dict(plan, action="show", reference=ref)
    m = re.search(r"(?:find|search for|show me|i want|look for)\s+(?:a\s+|an\s+|some\s+)?(.+)", low)
    if m:
        query = re.split(r"\b(?:without|with no|that excludes)\b", m[1])[0]
        query = re.sub(r"\brecipes?\b", "", query).strip(" .?")
        return dict(plan, action="search", query=query, include=[], pantry=[])
    if plan:
        return dict(plan, action="refine")
    return {"action":"unknown"}


class Chatbot:
    def __init__(self, store):
        self.store, self.state = store, State()

    def resolve(self, reference):
        if reference == "selected":
            if not self.state.selected_id: raise ValueError("Select a base recipe first using /search and /show 1.")
            return self.state.selected_id
        if str(reference).isdigit():
            index = int(reference)-1
            if not 0 <= index < len(self.state.last_ids): raise ValueError("That result number is not in the last displayed result list.")
            return self.state.last_ids[index]
        return str(reference)

    def ask(self, text):
        before = copy.deepcopy(self.state)
        try:
            plan = parse(text, self.state)
            self.validate(plan)
            action = plan["action"]
            if action in {"help", "unknown", "unavailable", "quit"}:
                return {"kind":action, "message": {"help":HELP, "unknown":"I could not interpret that request reliably. Use /help or an exact command; no filters changed.", "unavailable":"The dataset has no standardized nutrition or cooking-time fields. I will not invent exact values. Use /show 1 to inspect the original instructions for any stated timing.", "quit":"Goodbye."}[action]}
            if action == "reset":
                self.state=State()
                return {"kind":"state", "message":"All session context cleared.", "state":self.state.__dict__}
            if action == "scope": return {"kind":"state", "state":copy.deepcopy(self.state.__dict__)}
            for key in ("query", "include", "pantry", "max_steps", "preference"):
                if key in plan: setattr(self.state, key, copy.deepcopy(plan[key]))
            self.state.include = sorted({canonical(x) for x in self.state.include if canonical(x)})
            for key in ("include", "exclude"):
                current = getattr(self.state, key)
                current.extend(canonical(x) for x in plan.get("add_"+key, []) if canonical(x))
                setattr(self.state, key, sorted(set(current)))
            self.state.exclude = [x for x in self.state.exclude if x not in {canonical(y) for y in plan.get("allow", [])}]
            limit = plan.get("limit", 5)
            filters = self.state.filters()
            if action == "fact":
                recipe=self.store.recipe(self.resolve(plan.get("reference","selected")))
                attribute=plan["attribute"]
                evidence=([item["raw"] for item in recipe["normalized_ingredients"] if contains(item["name"],plan["target"])]) if attribute=="ingredient" else []
                return {"kind":"fact", "id":recipe["id"], "title":recipe["title"], "attribute":attribute, "target":plan.get("target"), "value":evidence if attribute=="ingredient" else recipe[attribute], "evidence":evidence, "rule":"Ingredient facts quote original lines matching a normalized whole-token family. No matching line is not a certification of absence. Counts use the documented normalized-line / text-segmentation rules."}
            if action == "show":
                rid = self.resolve(plan.get("reference","selected"))
                recipe = self.store.recipe(rid)
                self.state.selected_id=rid
                return {"kind":"recipe", "recipe":recipe, "restriction_violations":violations(recipe["ingredients"],self.state.exclude), "note":"Original source record; viewing a recipe does not certify that it meets active restrictions."}
            if action == "adapt":
                rid = self.resolve(plan.get("reference","selected"))
                result = adapt(self.store,rid,plan["target"],self.state.exclude)
                self.state.selected_id=rid
                self.state.exclude=sorted(set(self.state.exclude+[canonical(plan["target"])]))
                return result
            if action == "stats":
                return {"kind":"stats", **self.store.analytics(filters,plan.get("metric","count"),limit)}
            if action in {"search","match"}: self.state.mode=action
            if self.state.mode == "match" and self.state.pantry:
                result = match(self.store,filters,self.state.pantry,limit,self.state.preference)
                recipes=[x["recipe"] for x in result["results"]]
            else:
                total, recipes = self.store.search(filters,limit)
                result={"kind":"search", "filters":filters, "recipes_analyzed":total, "results":recipes, "screening":"Excluded ingredient text screened; product labels and cross-contact are not verified. No constraints relaxed."}
            self.state.last_ids=[r["id"] for r in recipes]
            self.state.selected_id=self.state.last_ids[0] if self.state.last_ids else None
            return result
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
            self.state=before
            return {"kind":"error", "message":str(exc), "state_changed":False}

    @staticmethod
    def validate(plan):
        if not isinstance(plan,dict): raise ValueError("A plan must be a JSON object.")
        allowed={"action","query","include","pantry","max_steps","preference","add_include","add_exclude","allow","limit","reference","target","metric","attribute"}
        if set(plan)-allowed: raise ValueError("Unknown plan field(s): "+", ".join(sorted(set(plan)-allowed)))
        if plan.get("action") not in {"search","match","refine","stats","show","fact","adapt","help","unknown","unavailable","quit","reset","scope"}: raise ValueError("Unknown action")
        for key in ("include","pantry","add_include","add_exclude","allow"):
            if key in plan and (not isinstance(plan[key],list) or not all(isinstance(x,str) and x.strip() for x in plan[key]) or len(plan[key])>50): raise ValueError(key+" must be a list of up to 50 nonempty strings")
        for key in ("query","target","reference","preference","metric"):
            if key in plan and not isinstance(plan[key],str): raise ValueError(key+" must be a string")
        if "max_steps" in plan and plan["max_steps"] is not None and (type(plan["max_steps"]) is not int or plan["max_steps"]<0): raise ValueError("max_steps must be a nonnegative integer or null")
        if "limit" in plan and (type(plan["limit"]) is not int or not 1<=plan["limit"]<=20): raise ValueError("limit must be 1..20")
        if "preference" in plan and plan["preference"] not in {"fewest_missing","use_most","fewest_steps"}: raise ValueError("Unknown ranking preference")
        if "metric" in plan and plan["metric"] not in {"count","average","median","common","fewest_steps","most_steps"}: raise ValueError("Unknown statistic")
        if plan["action"]=="adapt" and not plan.get("target","").strip(): raise ValueError("An adaptation needs a target ingredient.")
        if plan["action"]=="fact" and plan.get("attribute") not in {"ingredient","ingredient_count","step_count"}: raise ValueError("Unsupported recipe attribute")
        if plan["action"]=="fact" and plan["attribute"]=="ingredient" and not plan.get("target","").strip(): raise ValueError("An ingredient fact needs a target ingredient")


def render(response):
    kind=response["kind"]
    if kind in {"help","unknown","unavailable","error","quit"}: return response["message"]
    if kind=="state": return json.dumps(response,indent=2,ensure_ascii=False)
    if kind=="recipe":
        r=response["recipe"]
        return f"{r['title']} [{r['id']}]\n\nORIGINAL INGREDIENTS\n"+"\n".join("- "+x for x in r["ingredients"])+"\n\nORIGINAL INSTRUCTIONS\n"+r["instructions"]+"\n\n"+response["note"]+f"\nActive restriction violations: {response['restriction_violations']}"
    if kind=="stats": return json.dumps(response,indent=2,ensure_ascii=False)
    if kind=="fact": return json.dumps(response,indent=2,ensure_ascii=False)
    if kind=="adapt": return json.dumps(response,indent=2,ensure_ascii=False)
    lines=["Active filters: "+json.dumps(response["filters"]),f"Eligible population analyzed: {response['recipes_analyzed']:,}"]
    if not response["results"]: lines.append("No match found. No hard constraint was relaxed.")
    if kind=="match": lines.extend(["Ranking: "+response["ranking"],response["quantity_note"]])
    for i,item in enumerate(response["results"],1):
        r=item["recipe"] if kind=="match" else item
        lines.append(f"\n{i}. {r['title']} [{r['id']}] | {r['step_count']} counted steps")
        if kind=="match":
            lines.extend(["Matched: "+", ".join(item["matched"]),"Missing / extra required: "+", ".join(item["missing"]),"Unused available: "+", ".join(item["unused_available"]),f"Coverage: {item['coverage_percent']}%; rank key: {item['rank_key']}","Quantity checks: "+json.dumps(item["quantity_checks"])])
        lines.append("Ingredient evidence: "+"; ".join(x["raw"] for x in r["normalized_ingredients"]))
    lines.append(response.get("screening",response.get("constraint_note","")))
    if response["results"]: lines.append("Use /show 1 for the full original record. 'This recipe' refers to result 1 until you select another.")
    return "\n".join(lines)
