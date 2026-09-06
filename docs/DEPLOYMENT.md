# Deployment

How this app is deployed, and the concrete record of what is configured for the live
instance. Configuration values themselves live in [CONFIGURATION.md](CONFIGURATION.md).

---

## Set up the spend backstop first

The demo answers over a public URL on the owner's API key. App-side guardrails
(rate limits, input caps, and optionally a password gate — see [CONFIGURATION.md](CONFIGURATION.md))
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
   # APP_PASSWORD = "share-this-with-reviewers"   # omit to leave the app open
   # RATE_LIMIT_PER_HOUR = "20"
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
  `RATE_LIMIT_PER_HOUR = "20"`, which now matches the code default and is kept as an
  explicit record (rationale in [CONFIGURATION.md](CONFIGURATION.md#why-the-default-is-20)).
  `APP_PASSWORD` is **not** set: it gated the app while access was restricted, and was removed
  when the demo was opened up. Re-adding the secret re-enables the gate with no code change.
- **Viewer access: public.** Settings → Sharing is set to anyone-with-the-link. It was
  restricted to named viewers while the deployment was being proven out; that was lifted, and
  `APP_PASSWORD` was removed at the same time, since a password prompt would have left a
  reviewer just as stuck as a sharing wall. Cost is now bounded by `RATE_LIMIT_PER_HOUR = 20`,
  the per-session and input caps, and the workspace spend limit.
  **To close it again:** flip Sharing back to specific viewers, or re-add the `APP_PASSWORD`
  secret — either works on its own, neither needs a code change.
- No `pysqlite3-binary` shim was needed — the build succeeded against ChromaDB as-is on
  Streamlit's current base image. If a future redeploy hits `unsupported version of sqlite3`,
  see the fallback above.

### Not recorded here, on purpose

The actual API key, and the exact spend-limit and alert dollar amounts. Those live only in
the Anthropic Console and Streamlit secrets, never in this repo. (`APP_PASSWORD` is no longer
set at all — see above.)

---

## Smoke test after a redeploy

> **Due now.** Two rounds of change are live but unverified against the deployed app: the
> review pass (two ingest bug fixes, `thinking` disabled, dependency majors capped — which
> means the redeploy reinstalls from a newly resolved dependency set and cold-starts a fresh
> index), and the access change (public sharing, `APP_PASSWORD` removed,
> `RATE_LIMIT_PER_HOUR` lowered to 20). Run the sequence below and update this section.

Last run **2026-09-05**, against the deployed app: the `APP_PASSWORD` gate prompted and
unlocked correctly; a question from `tests/eval_set.json` against the auto-indexed sample docs
returned a grounded answer with the correct file cited in Sources; the sidebar uploader was
also tested with an external `.md` file (not part of this repo), confirming ingestion and
retrieval work for user-supplied documents and not just the bundled samples.

Repeat that sequence any time to confirm a redeploy still works end to end:

1. Open the link in a private window → expect the chat directly, with no sign-in and no
   password prompt.
2. One question from `tests/eval_set.json` → expect a grounded answer citing the right file.
3. One question the samples cannot answer → expect "I don't know", not a guess.
4. Optionally, upload a file and ask about it.

The 2026-09-05 run above included a password step that no longer exists; the sequence here is
the current one.
