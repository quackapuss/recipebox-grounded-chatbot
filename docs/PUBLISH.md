# Publication record

The project is published at [quackapuss/recipebox-grounded-chatbot](https://github.com/quackapuss/recipebox-grounded-chatbot).

- Source upload verified at commit `47319f25aabbc6f5710a8d4282963ce239c9508f`.
- The repository's existing MIT license and initial commit were preserved by merging histories.
- Public access was verified with an unauthenticated clone.
- [GitHub Actions passed on Python 3.11, 3.12 and 3.13](https://github.com/quackapuss/recipebox-grounded-chatbot/actions/runs/42333207380).
- Source, tests, README, Markdown/PDF roadmap, evaluation and dataset attribution are included.
- Downloaded raw data, the generated database and local caches are excluded by `.gitignore`.
- No recruiter message or assignment-form submission was sent.

Publication used local Git after the user completed Git Credential Manager's official GitHub device authorization as `quackapuss`. The separate connected GitHub integration was used for repository inspection and Actions verification.

## Clone and run

```shell
git clone https://github.com/quackapuss/recipebox-grounded-chatbot.git
cd recipebox-grounded-chatbot
python -m recipebox setup
python -m recipebox chat
```

Python 3.11+ with SQLite FTS5 is required. Setup downloads and imports all three official JSON files; no API key is needed. The offline deliverable already contains the generated database and can skip setup.

## Reproduce checks

```shell
python -m unittest discover -s tests -v
python -m recipebox evaluate
```

The public repository URL is the assignment submission link. Review the README, roadmap, limitations and AI disclosure before the interview.
