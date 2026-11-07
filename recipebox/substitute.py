"""Evidence-first, whole-variant adaptation; no invented substitution ratios."""
import re
from .normalize import canonical, violations

# Candidate role hypotheses guide retrieval. They are not empirical evidence.
ROLES = {
    "egg": ("binding, moisture and structure", ["applesauce", "banana", "flax", "chia", "yogurt", "yoghurt"], "The crumb and rise may change; these are predictions, not a tested outcome."),
    "cream": ("moisture, richness and sauce texture", ["coconut milk", "coconut cream", "cashew", "almond milk", "soy milk", "oat milk", "tomato"], "Flavor, fat level and sauce thickness may change; these are predictions, not a tested outcome."),
    "butter": ("fat, moisture and texture", ["oil", "applesauce", "coconut"], "Spread, richness and texture may change; these are predictions, not a tested outcome."),
    "milk": ("liquid, moisture and flavor", ["coconut milk", "almond milk", "soy milk", "oat milk", "water"], "Flavor and richness may change; these are predictions, not a tested outcome."),
}
TITLE_STOP = {"a", "an", "the", "and", "with", "best", "easy", "simple", "homemade", "recipe", "recipes", "vegan", "vegetarian", "eggless", "free", "gluten", "dairy", "low", "fat", "ii", "iii", "i", "s"}


def title_terms(title):
    return [x for x in re.findall(r"[a-z]+", title.lower()) if x not in TITLE_STOP]


def similarity_key(name):
    """Related-variant retrieval only; never changes exact pantry identity."""
    return re.sub(r"^(?:unbleached|bleached) all purpose flour$", "all purpose flour", name)


def adapt(store, rid, target, exclusions, limit=3):
    base = store.recipe(rid)
    target = canonical(target)
    terms = title_terms(base["title"])
    exclusions = sorted(set([canonical(x) for x in exclusions]+[target]))
    result = {"kind": "adapt", "base_id": rid, "base_title": base["title"], "target": target, "restrictions": exclusions, "base_recipe": base, "external_sources": [], "evidence_type": "Indirect local variant comparison; no controlled substitution experiment.", "safety": "Recipe-text screening cannot establish medical allergy safety, product composition or cross-contact safety."}
    target_lines = violations(base["ingredients"], [target])
    if not target_lines:
        return dict(result, status="unsupported", reason="The target ingredient was not found in the base ingredient text. Choose the exact ingredient or product.", candidates=[])
    role_key = next((k for k in ROLES if re.search(r"\b"+k+r"\b", target)), None)
    if not role_key or not terms:
        return dict(result, status="unsupported", reason="No role-aware adaptation policy is available for this target. Local evidence does not justify inventing a replacement or ratio.", candidates=[])
    role, proposals, effects = ROLES[role_key]
    base_names = {x["name"] for x in base["normalized_ingredients"] if not violations([x["raw"]], [target])}
    base_families = {similarity_key(x) for x in base_names}
    # Search local same-dish title anchors, not arbitrary top-k semantic hits.
    where, args = store.predicate({"exclude": exclusions})
    if {"banana", "bread"} <= set(terms):
        anchors = ["banana", "bread"]
    else:
        anchors = next(([x] for x in ("pasta", "penne", "spaghetti", "fettuccine", "cake", "muffin", "bread", "soup") if x in terms), terms[-2:])
    candidates = []
    all_ids = store.db.execute(f"SELECT r.id,r.title FROM recipe r WHERE {where}", args)
    inspected = 0
    for row in all_ids:
        donor_terms = set(title_terms(row["title"]))
        if not all(x in donor_terms for x in anchors) or row["id"] == rid:
            continue
        inspected += 1
        donor = store.recipe(row["id"])
        names = {x["name"] for x in donor["normalized_ingredients"]}
        shared = base_names & names
        families = {similarity_key(x) for x in names}
        shared_families = base_families & families
        overlap = len(shared_families)/len(base_families | families) if base_families | families else 0
        additions = names-base_names
        plausible = sorted(x for x in additions if any(p in x for p in proposals))
        if len(shared_families) < 3 or overlap < .45 or not plausible:
            continue
        # Both ingredient list and preparation text must pass restrictions.
        if violations([donor["instructions"]], exclusions):
            continue
        methods = [w for w in ("bake", "mix", "simmer", "boil", "stir", "blend", "whisk", "fry") if re.search(r"\b"+w, base["instructions"].lower()) and re.search(r"\b"+w, donor["instructions"].lower())]
        if not methods:
            continue
        candidates.append({"evidence_id": donor["id"], "evidence_title": donor["title"], "candidate_ingredients": plausible, "shared_ingredients": sorted(shared), "shared_similarity_families":sorted(shared_families), "similarity_jaccard": round(overlap,4), "similarity_policy":"For related-variant retrieval only, bleached/unbleached all-purpose flour share a family. Pantry identity and exact product differences remain separate.", "shared_methods": methods, "added_products": sorted(names-base_names), "removed_products_beyond_target": sorted(base_names-names), "updated_ingredients": donor["ingredients"], "revised_instructions": donor["instructions"], "revised_steps": donor["steps"], "role_hypothesis": role, "predicted_effects": effects, "quantity_policy": "Use this complete cited variant's own quantities and method. No one-to-one replacement ratio has been inferred.", "adaptation_method": "Whole related-variant adaptation: the complete ingredient list and instructions below are copied from the cited local donor, not an untested token edit of the base.", "confounding": "Other quantities/products/methods may differ. Co-occurrence supports feasibility in the donor, not causality or equivalence to the base."})
    candidates.sort(key=lambda c: (-c["similarity_jaccard"], len(c["added_products"])+len(c["removed_products_beyond_target"]), c["evidence_id"]))
    result.update(candidates=candidates[:limit], related_variants_inspected=inspected, role_hypothesis=role, search_rule=f"Titles contain anchors {anchors}; at least 3 shared product families; Jaccard >= 0.45; a shared method; a newly present role candidate; all exclusions screened in ingredients and instructions. Bleached/unbleached all-purpose flour share a similarity family only.")
    if candidates:
        result.update(status="supported_variant", reason="Local variants support an alternative complete preparation. The isolated ingredient swap remains unverified.")
    else:
        result.update(status="unsupported", reason="No sufficiently related, restriction-compatible local variant passed the evidence threshold. I cannot support a reliable adaptation from this evidence.")
    return result
