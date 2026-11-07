# Publish the prepared source

The assignment asks for a publicly accessible GitHub repository. The user selected [quackapuss/recipebox-grounded-chatbot](https://github.com/quackapuss/recipebox-grounded-chatbot), which exists and is public. The source is prepared locally, but upload is pending authenticated write access. Check `SUBMISSION_STATUS.md` for the verified publication state; do not assume this document means source publication happened.

Recommended repository name: `recipebox-grounded-chatbot`.

The public repository already exists. Do not upload the `data` directory, the offline database, downloaded archive, or local caches. The project `.gitignore` excludes them.

From the source folder, with Git installed and authenticated:

```shell
git init
git add .
git commit -m "Build grounded Recipe Box conversational assistant"
git branch -M main
git remote add origin https://github.com/quackapuss/recipebox-grounded-chatbot.git
git push -u origin main
```

Confirm the public repository and uploaded source can be opened while signed out. Test the README commands from a fresh clone, and submit that verified URL. The included GitHub Actions workflow runs synthetic tests; the large data download remains an explicit local evaluation step.

The current GitHub connection reports read access only (`push: false`) for the selected repository. Connect an account with write access before attempting publication. The integration can update the source once that access is available.
