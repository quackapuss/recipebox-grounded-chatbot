# Evaluation report

Executed on 7 November 2026. This report describes actual local runs, with the dataset snapshot identified by the accompanying manifest.

The uploaded source also passed [GitHub Actions on Python 3.11, 3.12 and 3.13](https://github.com/quackapuss/recipebox-grounded-chatbot/actions/runs/42333207380). Public cloning without authentication succeeded. The source was published at commit `47319f25aabbc6f5710a8d4282963ce239c9508f`; later publication/documentation commits do not change application behavior.

- Unit tests: **17 / 17 passed** using a synthetic known-answer dataset.
- Full-data checks: **17 / 17 passed** across eight executed conversations.
- Runtime: Python 3.11.9, SQLite 3.45.1.
- Raw source records: **125,164**; searchable records: **122,935**; invalid/incomplete records preserved but excluded from search: **2,229**.

## Dataset coverage

| Source | Raw | Searchable | Invalid / incomplete |
|---|---:|---:|---:|
| ar | 39,802 | 39,522 | 280 |
| epi | 25,323 | 25,260 | 63 |
| fn | 60,039 | 58,153 | 1,886 |

1,695 subsequent records had an exact title/ingredients/instructions content hash already seen. These records are retained. This is a diagnostic count, not a deduplication policy.

## Exact analytical results

The garlic-and-onion query returned **21,399 / 122,935 = 17.406760%**. The denominator is all searchable records. Include predicates require the normalized ingredient name to contain each whole-token phrase, so forms such as garlic powder can count toward the garlic family. Source duplicates remain separate records. An independent ordered Python ingredient scan reproduced the SQL-backed count.

The tomato-family population contained **19,016** records. Mean ingredient-line count was **13.411653**; median was **12**. These use the complete filtered population, not the five displayed recipes.

| Fewest-step title | Stable ID | Counted steps |
|---|---|---:|
| Tomato Basil Smoothie | ar:/0wx00RefE0VHzlff/GBszObKmj63Pi | 1 |
| Best Ever Kabob Marinade | ar:3wzVv1X6HjgIShD5L9GKsL1ug4SvAPi | 1 |
| Mediterranean Zucchini and Chickpea Salad | ar:3yxgq0iAqrlm2lHnLoxwJ8vQTHCd/Cm | 1 |
| Momma's Marinara Sauce | ar:5s.4S6mTsQWRNXHDFGWe6ea03Oac48C | 1 |
| Black Bean and White Corn Salad | ar:9T2HkniyS.3VZB9NmFvzrfA39fMSt.. | 1 |

Ties are resolved by stable ID. Step counts use nonempty newline paragraphs, or sentence boundaries when instructions are one paragraph. A one-step source paragraph can contain several cooking actions; this is a text-segmentation ranking, not a difficulty judgment.

## Executed conversations and timing

| Conversation | Seconds |
|---|---:|
| 1. Search, persistent dairy restriction, and original recipe | 0.087 |
| 2. Exact aggregate and follow-up percentage | 5.573 |
| 3. Global filtered ranking and descriptive statistics | 16.256 |
| 4. Pantry matching and an additional hard restriction | 5.679 |
| 5. No match and empty aggregate | 0.425 |
| 6. Egg removal using local banana-bread variants | 1.412 |
| 7. Weak or conflicting egg-replacement evidence | 1.480 |
| 8. Unsupported nutrition and quantity-aware name matching | 3.504 |

Timings are observed local elapsed execution for each conversation's turns. They exclude setup and the independent aggregate oracle. They are not a production latency benchmark. Full original responses are in `test_conversations.md`.

## Evidence-backed adaptation

The deterministic banana-bread base was `ar:BoBTO3QUO3Ci.0kayPs8.CfDU5oEXuu`. Final status: `supported_variant`. Local donor IDs: `fn:p174TykunvO./PLjDpl03RBTaXiOEdu`.

The donor is a complete observed eggless banana-bread variant with soy-milk yogurt. The output copies its ingredient quantities and complete preparation. The flour-family similarity mapping is used for related-variant retrieval only; exact pantry identities remain distinct. This evidence is indirect and confounded by other recipe changes. It does not prove that yogurt alone can replace eggs at a particular ratio in the base.

The weak-evidence meringue case refused to manufacture an egg replacement. This is intended behavior because a generic binding/moisture candidate does not establish the structural function needed by that selected dish.

## What initially failed and why

The first full-data run passed 15 of 16 checks. The banana-bread adaptation missed a relevant Food Network variant because exact flour identity reduced relatedness below the Jaccard threshold. The fix introduced a narrowly scoped bleached/unbleached all-purpose-flour family projection for adaptation similarity, preserving strict pantry identity. The same base then retrieved the cited variant; the evidence threshold was unchanged.

The first tomato-statistics conversation took about 60 seconds. Reusing a selected-ID population for ingredient-frequency grouping reduced the observed scenario to about 16 seconds in the next run. Broad-filter queries remain slower than lexical search; these are local measurements, not guarantees.

## Final checks

| Check | Result |
|---|---|
| search returns real IDs | PASS |
| follow-up retains dish and excludes dairy | PASS |
| original instructions retrievable | PASS |
| selected-recipe Q&A cites original ingredient lines | PASS |
| aggregate equals independent full-record scan | PASS |
| follow-up denominator and scope persist | PASS |
| step ranking uses tomato population | PASS |
| average median common use same full scope | PASS |
| pantry five eligible existing recipes | PASS |
| pantry restriction follow-up persists | PASS |
| pantry result keys are ordered | PASS |
| no match does not relax restrictions | PASS |
| empty average is null | PASS |
| banana adaptation cites compatible complete variants | PASS |
| weak structural-egg evidence is refused | PASS |
| nutrition answer refuses fabrication | PASS |
| quantity checks exposed | PASS |

## One-shot answer comparison

This is an explicitly **illustrative AI-authored one-shot-style answer**, not a sampled external-model API response and not a measured model benchmark.

User: How many calories does this recipe have?

Ungrounded illustrative answer: This recipe has exactly 350 calories per serving.

Why it fails: no standardized nutrition or dependable serving-yield fields support that number.

Actual chatbot behavior: refuses to invent exact nutrition and offers the original instructions as the available source.

## What worked and what remains limited

Complete-source ingestion, stable IDs, original text retrieval, persistent restrictions, exact population statistics, deterministic pantry ranking, comparable quantity reporting, supported local-variant retrieval, and weak-evidence abstention passed the recorded checks.

The language router supports a bounded grammar. Product normalization and allergen vocabulary are heuristic. Unknown brands, compound products, optional alternatives, and source noise can cause missed equivalences or conservative exclusions. Ingredient-text absence does not prove medical safety. Quantity parsing does not cover ranges, packaging, densities or yield. Substitution is whole-variant adaptation, not a validated isolated edit. No external LLM/API baseline was measured. The small suite is not a global retrieval-accuracy or food-safety certification.

## Reproduce

```shell
python -m unittest discover -s tests -v
python -m recipebox evaluate
```

`evaluate` exits with a failure status if any recorded check fails. Check source hashes before comparing results from a newly downloaded archive.
