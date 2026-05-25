# Security

This repository is **public**. Treat it as untrusted by default.

## Never commit

- `.env`, credentials, API tokens, Notion tokens
- `*.db`, `data/`, Playwright session files
- `/etc/monmarche/htpasswd` or any password files

Only `.env.example` with placeholders belongs in git.

## Production secrets

Secrets live **only** on the VPS:

- `/opt/monmarche/backend/.env` (mode `600`, owner `monmarche`)
- `/etc/monmarche/htpasswd` (mode `640`, owner `root`)

Authentication in production uses **browser session cookies** (`/auth/login`), not Bearer tokens in client code.

## If a secret is exposed

1. Rotate the token immediately (Notion integration, htpasswd user, etc.)
2. Revoke active sessions in SQLite (`user_sessions`) or restart with new cookie secret flow
3. Do not rely on `git revert` alone — assume the secret is compromised

## Reporting

Private project — contact the repository owner directly.
