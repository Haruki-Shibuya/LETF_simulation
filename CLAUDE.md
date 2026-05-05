# LETF Simulation — Claude Instructions

## Git sync rule

Always run `git push origin main` immediately after every `git commit`. Local and remote must stay in sync at all times. Never leave commits unpushed.

## Never commit secrets

Never `git add` any of the following under any circumstances:
- `.env` or any `*.env` file
- Any file containing an API key, app key, token, or password
- Any file whose name or content suggests credentials

If a secret is needed for a script, read it from an environment variable or `.env` file and ensure `.env` is in `.gitignore` before the first commit.
