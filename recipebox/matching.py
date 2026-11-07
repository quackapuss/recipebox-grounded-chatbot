"""Explainable full-population pantry ranking and conservative quantity checks."""
from collections import defaultdict
from .normalize import canonical, quantity


def quantity_check(pantry, recipe):
    available, required = defaultdict(list), defaultdict(list)
    for raw in pantry:
        available[canonical(raw)].append(quantity(raw))
    for item in recipe["normalized_ingredients"]:
        required[item["name"]].append(quantity(item["raw"]))
    checks = []
    for name in sorted(set(available) & set(required)):
        a, r = available[name], required[name]
        dims = {q[0] for q in a+r if q}
        if any(q is None for q in a+r) or len(dims) != 1:
            checks.append({"ingredient": name, "status": "not_verified", "reason": "Missing/ambiguous quantity, package/range, or incompatible dimensions. No density conversion."})
        else:
            av, req = sum(q[1] for q in a), sum(q[1] for q in r)
            checks.append({"ingredient": name, "status": "sufficient" if av+1e-8 >= req else "insufficient", "available": round(av, 4), "required": round(req, 4), "dimension": next(iter(dims))})
    return checks


def match(store, filters, pantry, limit=5, preference="fewest_missing"):
    keys = sorted({canonical(x) for x in pantry if canonical(x)})
    if not keys:
        raise ValueError("Provide at least one ingredient.")
    where, values = store.predicate(filters)
    marks = ",".join("?" for _ in keys)
    # Every eligible recipe sharing at least one exact product is considered.
    rows = store.db.execute(f"""SELECT r.id,r.title,r.step_count,
      count(DISTINCT i.name) AS required,
      count(DISTINCT CASE WHEN i.name IN ({marks}) THEN i.name END) AS matched
      FROM recipe r JOIN ingredient i ON i.recipe_id=r.id WHERE {where}
      GROUP BY r.id HAVING matched>0""", keys+values).fetchall()
    def rank(row):
        missing = row["required"] - row["matched"]
        score = 100*row["matched"]/row["required"]
        if preference == "use_most":
            return (-row["matched"], missing, -score, row["step_count"], row["id"])
        if preference == "fewest_steps":
            return (row["step_count"], missing, -row["matched"], -score, row["id"])
        return (missing, -row["matched"], -score, row["step_count"], row["id"])
    ranked = sorted(rows, key=rank)
    results = []
    for row in ranked[:limit]:
        r = store.recipe(row["id"])
        needed = {i["name"] for i in r["normalized_ingredients"]}
        matched = sorted(needed & set(keys))
        missing = sorted(needed - set(keys))
        results.append({"recipe": r, "matched": matched, "missing": missing, "extra_required_ingredients": missing, "unused_available": sorted(set(keys)-needed), "coverage_percent": round(100*len(matched)/len(needed), 2), "rank_key": list(rank(row)), "quantity_checks": quantity_check(pantry, r)})
    return {"kind": "match", "filters": filters.copy(), "pantry": pantry[:], "preference": preference, "recipes_analyzed": len(rows), "results": results, "ranking": {"fewest_missing": "Fewest distinct missing products; most matched products; highest coverage; fewest steps; stable ID.", "use_most": "Most matched pantry products; fewest missing; highest coverage; fewest steps; stable ID.", "fewest_steps": "Fewest steps; fewest missing; most matched; highest coverage; stable ID."}[preference], "quantity_note": "Name-level ranking. Quantity sufficiency is verified only for comparable parsed measurements (US volume units); per-ingredient checks below. No quantity guarantees for unchecked or missing products.", "constraint_note": "Hard constraints applied before ranking. No constraints were relaxed. Ingredient-text screening does not establish allergen or cross-contact safety."}
