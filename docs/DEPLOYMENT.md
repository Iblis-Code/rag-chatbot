# Deployment

How this app is deployed, and the concrete record of what is configured for the live
instance. Configuration values themselves live in [CONFIGURATION.md](CONFIGURATION.md).

---

## Set up the spend backstop first

The demo answers over a public URL on the owner's API key. App-side guardrails
(rate limits, input caps, the password gate — see [CONFIGURATION.md](CONFIGURATION.md))
bound the blast radius, but the limit a bug or a scripted abuser **cannot** exceed is set in
the Anthropic Console. Do this before the app goes live:

1. Create a dedicated **Workspace** at
   [platform.claude.com/settings/workspaces](https://platform.claude.com/settings/workspaces)
   and mint an API key *inside* it. Scoping the key to its own workspace means it can be
   capped or revoked in isolation, without touching any other API usage on the account.
2. On the workspace's **Limits** tab, set a **monthly spend limit**. When it is reached the
   key errors and the app stops answering — the bill cannot exceed it.
3. Add **usage alert notifications** (via **Add notification**) so a threshold email arrives
   before the hard cap is hit.

That scoped key is the `ANTHROPIC_API_KEY` secret in the next section.

## Deploy to Streamlit Community Cloud

1. Push the repo to public GitHub.
2. At [share.streamlit.io](https://share.streamlit.io) → **New app** → pick the repo and
   branch, set **main file** to `app.py`.
3. **Advanced settings** → Python **3.12** (matches `.python-version`).
4. **Secrets** → paste (see [`.streamlit/secrets.toml.example`](../.streamlit/secrets.toml.example)):
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."   # the workspace-scoped key
   # optional guardrail overrides:
   # APP_PASSWORD = "share-this-with-reviewers"
   # RATE_LIMIT_PER_HOUR = "60"
   ```
5. **Deploy.** First load takes ~1–2 min while the MiniLM model downloads; `data/samples/`
   is indexed automatically on the first run.
6. Copy the app URL into the **Live demo** line at the top of the README.

### Notes

- The container disk is **ephemeral** — uploaded files and their index reset on every
  reboot. The committed `data/samples/` always reload, so the demo is never empty.
- If the build fails with `unsupported version of sqlite3`, uncomment `pysqlite3-binary`
  in `requirements.txt` and add this shim as the first lines of `app.py`:
  ```python
  __import__("pysqlite3")
  import sys; sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
  ```

---

## Deployment log (this instance)

Concrete record of what is actually configured for the live deployment — so a future change
(rotating the key, raising the cap, opening access) starts from what is true today instead of
guesswork. **Update this section whenever a setting below changes.**

### GitHub

- Repo: [Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot), public, branch `main`
- Commits authored as `Iblis-Code <275904533+Iblis-Code@users.noreply.github.com>`
  (set via `git config --global user.name` / `user.email` — real email kept out of commit
  history on purpose)
- `gh` CLI is authenticated as `Iblis-Code` locally (`gh auth status` to confirm/renew)

### Anthropic Console

- Dedicated workspace: **`rag-chatbot-demo`**, kept separate from any other API usage on this
  account so it can be capped or revoked in isolation
- API key minted *inside* that workspace and used as the `ANTHROPIC_API_KEY` Streamlit secret.
  The raw key value is not recorded anywhere in this repo, by design — if it is lost, revoke it
  in the Console, mint a new one, and update the Streamlit secret.
- Funded by **$5 of organizational credit**, explicitly a temporary prove-it-out budget, not a
  production allocation.
- Workspace **Limits** tab: a monthly spend cap set below the $5 credit (leaving a small
  buffer), plus email usage-alert notification(s). Exact dollar values were set interactively
  in the Console UI and are not tracked here — check or adjust them on that tab directly.
  They are the first thing to raise if the $5 credit is ever upgraded.

### Streamlit Community Cloud

- App URL: **https://rag-chatbot-project-1.streamlit.app/**
- Source: `Iblis-Code/rag-chatbot`, branch `main`, main file `app.py`
- Python version: **3.12** — matches `.python-version`, and deliberately not the 3.14 default
  Streamlit offered, to avoid torch/chromadb wheel issues on a brand-new Python
- Secrets (Settings → Secrets): `ANTHROPIC_API_KEY` (the `rag-chatbot-demo` key above) and
  `APP_PASSWORD` (a shared password chosen at deploy time — share it out-of-band with anyone
  you want to try the app; rotate by editing the same secret)
- **Viewer access: restricted.** Settings → Sharing is set to specific allowed viewers rather
  than "anyone with the link" — a deliberate choice while proving things out on the $5 credit,
  belt-and-suspenders alongside `APP_PASSWORD` and the app's rate limits.
  **To open it up:** Streamlit app → Settings → Sharing → switch to public / anyone-with-the-link.
  Nothing else needs to change; `APP_PASSWORD` and the app-side guardrails still apply after
  that switch.
- No `pysqlite3-binary` shim was needed — the build succeeded against ChromaDB as-is on
  Streamlit's current base image. If a future redeploy hits `unsupported version of sqlite3`,
  see the fallback above.

### Not recorded here, on purpose

The actual API key and `APP_PASSWORD` values, and the exact spend-limit and alert dollar
amounts. Those live only in the Anthropic Console and Streamlit secrets, never in this repo.

---

## Smoke test after a redeploy

> **Due now.** The code review pass that fixed the two ingest bugs, disabled `thinking`, and
> capped dependency majors has not yet been smoke-tested against the live app. The redeploy
> reinstalls from the newly capped `requirements.txt` and cold-starts a fresh index, so both
> the build and the first answer are worth watching. Run the sequence below and update this
> section with the result.

Last run **2026-09-05**, against the deployed app: the `APP_PASSWORD` gate prompted and
unlocked correctly; a question from `tests/eval_set.json` against the auto-indexed sample docs
returned a grounded answer with the correct file cited in Sources; the sidebar uploader was
also tested with an external `.md` file (not part of this repo), confirming ingestion and
retrieval work for user-supplied documents and not just the bundled samples.

Repeat that sequence any time to confirm a redeploy still works end to end:

1. Password gate → unlock.
2. One question from `tests/eval_set.json` → expect a grounded answer citing the right file.
3. One question the samples cannot answer → expect "I don't know", not a guess.
4. Optionally, upload a file and ask about it.
