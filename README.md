# Recipe Box: grounded conversational recipe assistant

Search, calculate dataset statistics, rank recipes against a pantry, and adapt a selected dish using cited local variants. Multi-turn state keeps restrictions active. Python 3.11+ and SQLite FTS5; **no API key and no runtime pip dependencies**.

## Run

From this directory:

```shell
python -m recipebox setup
python -m recipebox chat
```

Setup downloads the official archive, requires all three JSON files, preserves every raw record, and creates `data/recipes.sqlite3`. The download is about 51 MiB; allow several minutes for import and at least 2 GB of free disk space. If you received the ready-to-run ZIP with `data/recipes.sqlite3`, skip setup.

```text
Find a penne pasta recipe.
I cannot have dairy.
Show the first recipe.
/reset
How many recipes contain both garlic and onion?
What percentage of the dataset is that?
/reset
I have eggs, onions, tomatoes, and rice. No peanuts. At most six steps.
Exclude eggs too
/reset
/search banana bread
/show 1
Remove eggs from this recipe.
```

`/help` lists exact commands for supported operations; `/scope` shows state. `/json` accepts a validated structured plan. The natural-language router deliberately supports a bounded grammar and asks for an exact command when it cannot interpret a request reliably.

For full original ingredients and instructions, use `/show 1` or `/show source:original-key`. Source prefixes are `ar`, `epi`, and `fn`. The first displayed result becomes the selected recipe until you choose another. `/allow egg` removes that restriction; `/reset` clears all state. New dish and pantry searches keep restrictions and maximum steps until explicitly changed.

## Verify

```shell
python -m unittest discover -s tests -v
python -m recipebox evaluate
python -m recipebox ask "How many recipes contain both garlic and onion?" --json
```

Unit tests use a tiny synthetic dataset with known answers. Evaluation executes eight real-data conversations, an independent full-population aggregate check, and evidence/constraint checks. Results are in `docs/evaluation_results.json`; actual responses are in `docs/test_conversations.md`.

## Design and limits

- SQLite FTS5 with BM25 ranks title/ingredient search. Statistics use **all filtered records**, never just the five displayed results.
- Matching applies hard constraints before lexicographic ranking. It distinguishes garlic from garlic powder, tomato from tomato paste, egg from egg white, and cooked from uncooked rice. Family filters such as `tomato` deliberately include products whose normalized name contains that whole-token phrase.
- Quantities are checked only when measurements are comparable. Unchecked quantities are explicitly reported; no mass/volume density conversion is guessed. Name-level matching does not guarantee a complete pantry.
- Substitution retrieves related local variants first. It returns the complete cited variant's ingredient list and instructions, all product differences, and uncertainty. It does **not** claim a controlled or one-to-one replacement ratio. Weak evidence leads to refusal.
- Ingredient-text exclusions cannot establish medical allergy safety, undisclosed product composition, or cross-contact. Exact nutrition and standardized cooking times are unavailable.
- No runtime LLM or external culinary search is used. The included one-shot comparison is explicitly an illustrative AI-authored baseline, not an API benchmark.

See [the detailed roadmap](docs/ROADMAP.md), [requirement mapping](docs/REQUIREMENTS.md), and [evaluation report](docs/EVALUATION.md). These explain each module, every method, formulas, evidence policy, actual test results, limitations, and interview exercises.

## Data and disclosure

Data: [Recipe Box](https://eightportions.com/datasets/Recipes/) by Ryan Lee; three sources: Allrecipes, Epicurious, and Food Network. Source hash keys are preserved; original URLs are unavailable in the distributed files. `docs/data_manifest.json` records SHA-256 checksums, source counts, exclusions, and the duplicate policy. Dataset material retains its original license; see `DATA_LICENSE_NOTICE.md` and `docs/DATASET_LICENSE.txt`.

Codex assisted with requirements analysis, implementation, test design, debugging, and documentation. The implementation is supplied for review and study; the candidate must understand and be able to modify it in the interview. See `AI_DISCLOSURE.md`.

## Troubleshooting

If `No module named recipebox` appears, run from the folder containing this README. If FTS5 is missing, use a standard Python distribution whose SQLite includes FTS5. If setup fails during download, retry it; it never extracts arbitrary archive paths. An incomplete database is written to a temporary `.building` file and replaces the active database only after import succeeds. The optional `--data-dir PATH` argument selects another data directory.
