# Assignment requirement mapping

The source brief is the user-provided GenAI Intern Assignment. The table maps its requirements to concrete implementation and validation, without assigning an unsupported score.

| Requirement | Implementation | Evidence / qualification |
|---|---|---|
| All three JSON files | `store.build`, `__main__.setup` | Missing any source is an error; manifest stores source checksums and counts |
| Stable IDs and originals | `source:original_hash_key`, `raw_json`, ingredient/instruction columns | Raw invalid records retained; every result can be inspected by `/show` |
| Runnable conversational interface | `python -m recipebox chat` | Actual terminal run plus reproducible conversation evaluation |
| Dish and ingredient search | FTS5 over title and normalized ingredient text; explicit ingredient family filters | Bounded natural-language router plus exact commands; no embeddings |
| Context and persistent restrictions | `chat.State` | New restrictions refine current mode; explicit `/allow` and `/reset` |
| Specific recipe factual Q&A | `/show`, ordinal selection and full stable IDs | Full original ingredient list and instructions; no generated recipe facts |
| Counts and percentages | `Store.analytics` | Full filtered population; searchable-record denominator and formula displayed |
| Common ingredients | SQL distinct recipe frequency per normalized product | Full filtered population; duplicates within recipe count once for frequency |
| Average and median ingredient counts | SQL population extraction plus Python statistics | Ingredient-line rule stated; empty population returns null |
| Ranking by steps | SQL order over full filtered population | Explicit step rule and ID tie-break |
| No fabricated nutrition or timing | `unavailable` route | Standardized fields absent; show original instructions instead |
| Pantry names and optional quantities | `matching.match`, `quantity_check` | Exact product matching; compatible parsed quantities checked; unknowns disclosed |
| Hard constraints and preferences | SQL exclusions before ranking; three preference policies | No silent relaxation; recipe-text screening has stated limits |
| Matched, missing and extra ingredients | Set differences displayed per match | Extra required ingredients are the same set as missing pantry products; unused pantry is separate |
| No invented Task 2 recipes | Results are existing source IDs only | Full records attached to JSON responses |
| Role-aware, local-first substitution | `substitute.adapt` | Same-dish anchors, shared products and methods, role candidate, Jaccard threshold |
| Cite substitution support | Donor ID, title, shared products and methods | Indirect variant evidence, explicitly not causal proof |
| Updated ingredient list and revised instructions | Complete observed donor variant | Copies donor quantities and full method; does not claim a validated isolated swap |
| Taste/texture/preparation tradeoffs | Role hypotheses and predicted effects | Predictions labelled; no measured outcome claimed |
| Weak evidence and allergies | Abstention and text screening | No medical safety certification; unresolved or unknown evidence refused |
| At least five conversations | Eight executed conversations | `test_conversations.md` and machine-readable evaluation results |
| Reproducible small evaluation set | Fixture-based unit tests and fixed full-data scenarios | `tests/test_system.py` and `recipebox/evaluate.py` |
| One-shot answer failure | Explicit illustrative AI-authored nutrition baseline | Shows unsupported exact calories vs grounded refusal; no external API benchmark claimed |
| Explain decisions | `ROADMAP.md` | Algorithms, framework inventory, formulas, limitations, module walkthrough |
| AI assistance disclosure | `AI_DISCLOSURE.md` | States scope of Codex assistance and candidate review responsibilities |
| Public GitHub repo | Published at `quackapuss/recipebox-grounded-chatbot`; `PUBLISH.md` | Source upload and anonymous clone verified; existing repository license preserved |
| Clear short README | Root `README.md` | Two-command setup/run; offline bundle skips setup |

## Deliberate scope limits

The natural-language interface is a rule-based subset, not unrestricted conversational understanding. It covers the assignment examples and documents exact commands. It does not offer a general free-form culinary explanation engine.

The substitution method is conservative whole-variant adaptation. The full donor recipe is the revised output. The implementation does not assert that swapping only one product in the base while preserving all other base quantities is validated. This tradeoff prioritizes an observed, citeable preparation over unsupported synthesis.

The one-shot comparison is demonstrative, not a measured external-model experiment. API keys were not provided and no model API was invoked. A future benchmark should record provider/model/version, prompt, raw response, date, and generation parameters before evaluating grounding.
