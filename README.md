# RAG Chatbot — Chat with your documents

Ask questions and get answers grounded in **your own documents**, not the model's
training data. Documents are chunked, embedded, and stored in a vector database;
at query time the most relevant chunks are retrieved and passed to Claude, which
answers using only that context and cites the source file for each fact.

**Repo:** [github.com/Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot)
**Live demo:** [rag-chatbot-project-1.streamlit.app](https://rag-chatbot-project-1.streamlit.app/) — ⚠️ **viewer access currently restricted** to specific Streamlit accounts (Settings → Sharing), while it's being proven out on a $5 workspace credit. Not yet reachable by a bare link. To open it up: Streamlit Cloud app → **Settings → Sharing** → set to public/anyone-with-the-link; the app's own `APP_PASSWORD` guardrail still gates the chat/uploader after that.

## Status

| Part | State |
|---|---|
| Config, loaders, chunker, embeddings, vector store, ingest, chatbot | ✅ implemented + unit tested |
| Streamlit UI (`app.py`) | ✅ implemented + smoke tested (`AppTest`) |
| CLI scripts (`scripts/ingest_cli.py`, `scripts/eval_retrieval.py`) | ✅ implemented + tested |
| Test suite | ✅ `pytest`, 60 tests, **60/60 passing** (last run 2026-09-05) |
| Sample documents + `tests/eval_set.json` | ✅ 3 demo docs, 11-question eval set (**hit@4 = 1.00**) |
| GitHub repo | ✅ pushed — public, [Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot), branch `main` |
| Anthropic Workspace + key | ✅ `rag-chatbot-demo` workspace, scoped key, spend limit + usage alerts set ($5 credit) |
| Streamlit Cloud deploy | ✅ live at the URL above — Python 3.12, `APP_PASSWORD` set — but **viewer access restricted**, not public yet |
| Cost & abuse controls (rate limits, history cap, input cap, password gate) | ✅ implemented + tested — see [Cost & abuse controls](#cost--abuse-controls) |

The full build plan lives in [`docs/PLAN.md`](docs/PLAN.md).

## Publishing (in progress)

The code is complete and tested (60 passing tests), cost-control guardrails included.
It's deployed end-to-end; the one remaining decision is whether/when to open it to the public:

- [x] `git init` + first commit, push to a **public** GitHub repo — done: [Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot)
- [x] Create a dedicated **Anthropic Workspace**, mint a scoped API key, and set a
      **monthly spend limit + usage alerts** on it — done: `rag-chatbot-demo` workspace, $5 credit capped
- [x] Create the app at [share.streamlit.io](https://share.streamlit.io) — main
      file `app.py`, Python **3.12** — done
- [x] Add the scoped `ANTHROPIC_API_KEY` secret (Settings → Secrets); `APP_PASSWORD` set
- [x] Paste the resulting URL into the **Live demo** line at the top of this README
- [ ] Decide when to flip **Settings → Sharing** to public — currently restricted to
      specific viewers deliberately, while proving things out on the $5 credit

See [Deploy](#deploy) for the detailed walkthrough.

## How it works

```
                     ┌─────────── ingestion (one-time / on upload) ───────────┐
  your documents ──▶ load ──▶ chunk (overlap) ──▶ embed ──▶ ChromaDB (on disk)
  (pdf / txt / md)                                                    │
                                                                      ▼
        question ──▶ embed ──▶ similarity search (top-k) ──▶ relevant chunks
                                                                      │
                                      chunks + question + history ──▶ Claude
                                                                      │
                                                                      ▼
                                              grounded answer with [source] tags
```

- **Chunking** (`rag/chunker.py`) — paragraph-aware packing up to `CHUNK_SIZE`
  chars, oversized paragraphs split on word boundaries, each chunk prefixed with
  the tail of the previous one (`CHUNK_OVERLAP`) so context survives boundaries.
- **Embeddings** (`rag/embeddings.py`) — local `sentence-transformers`
  (`all-MiniLM-L6-v2`, 384-dim), unit-normalised for cosine similarity. No
  embedding API, no key, runs offline. Model loads lazily on first use.
- **Vector store** (`rag/vector_store.py`) — `ChromaVectorStore` behind a
  `VectorStore` interface (Pinecone slots in for Phase 2 with no call-site
  changes). Deterministic chunk IDs (`sha1(source:page:index)`) mean re-ingesting
  a file upserts instead of duplicating.
- **Generation** (`rag/chatbot.py`) — Claude via the official `anthropic` SDK,
  streamed. Retrieval happens eagerly (sources shown immediately); the token
  stream is lazy. If nothing relevant is retrieved, it says so instead of guessing.

## Project layout

```
project-1/
├── app.py                     # ✅ Streamlit UI (entry point)
├── rag/
│   ├── config.py              # ✅ env vars + constants (single source of truth)
│   ├── loaders.py             # ✅ pdf/txt/md -> list[Document]
│   ├── chunker.py             # ✅ text -> overlapping chunks
│   ├── embeddings.py          # ✅ sentence-transformers singleton
│   ├── vector_store.py        # ✅ VectorStore ABC + ChromaVectorStore
│   ├── ingest.py              # ✅ load -> chunk -> embed -> store
│   └── chatbot.py             # ✅ retrieve -> prompt -> stream answer + sources
├── scripts/
│   ├── ingest_cli.py          # ✅ python -m scripts.ingest_cli data/samples
│   └── eval_retrieval.py      # ✅ hit@k + MRR over a small Q->source set
├── data/samples/              # ✅ committed demo docs, auto-indexed on first run
│   ├── acme_handbook.md
│   ├── acme_analytics_faq.md
│   └── acme_security_policy.md
├── .streamlit/
│   ├── config.toml            # theme + upload size
│   └── secrets.toml.example   # secret format for local / Streamlit Cloud
├── tests/                     # ✅ 60 tests
│   ├── conftest.py            #    isolates ChromaDB to a temp dir per test
│   ├── helpers.py             #    test doubles (deterministic embedder, in-mem store)
│   ├── eval_set.json          #    11 question -> expected-source pairs
│   ├── test_chunker.py        #    chunking rules
│   ├── test_loaders.py        #    pdf/txt/md loading
│   ├── test_ingest.py         #    ingest pipeline (in-memory store)
│   ├── test_chatbot.py        #    faked Claude client
│   ├── test_scripts.py        #    ingest_cli + eval_retrieval
│   ├── test_app.py            #    Streamlit AppTest smoke
│   └── test_smoke.py          #    real end-to-end against ChromaDB (torch-free)
├── .env.example
├── .python-version            # Python 3.12 for Streamlit Cloud
├── requirements.txt           # runtime deps
├── requirements-dev.txt       # runtime + pytest
└── docs/PLAN.md
```

## Setup

```powershell
python -m venv .venv                     # Python 3.11-3.14 (Streamlit Cloud pin is 3.12)
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # includes torch via sentence-transformers
Copy-Item .env.example .env              # then add your ANTHROPIC_API_KEY
```

First embedding call downloads the ~90 MB MiniLM model and caches it locally.
For the test suite too, `pip install -r requirements-dev.txt`.

## Run

```powershell
streamlit run app.py
```

Then, in the browser:

1. On first launch the app indexes any files in `data/samples/` so there is
   something to ask about immediately. The sidebar shows the chunk count.
2. Add your own PDF / TXT / Markdown files with the sidebar uploader and click
   **Ingest uploaded files**; re-ingesting the same filename updates in place.
3. Ask questions in the chat box. Each answer streams in and is followed by a
   **Sources** panel listing the chunks it was grounded in. Questions with no
   relevant match get an "I don't know" instead of a guess.
4. **Clear index** empties the vector store; **Reset chat** clears the transcript.

Without `ANTHROPIC_API_KEY` set, indexing still works but the chat box is
disabled.

## Command line

```powershell
# Index files/directories into the persistent store (--reset to start fresh)
python -m scripts.ingest_cli data/samples
python -m scripts.ingest_cli --reset docs/ notes.md

# Retrieval quality: hit@k + MRR over tests/eval_set.json
python -m scripts.eval_retrieval --k 4
python -m scripts.eval_retrieval --min-hit-rate 0.8   # non-zero exit if below (CI)
```

`eval_retrieval` needs the store populated (run `ingest_cli` first) and an eval
set at `tests/eval_set.json` — a JSON list of
`{"question": "...", "expected_source": "file.md"}` items (`expected_sources` list
also accepted). Use it to tune `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K`.

On the bundled sample docs this scores **hit@4 = 1.00, MRR = 1.00** (11/11
questions retrieve the correct document first), with `all-MiniLM-L6-v2` and the
default 800/150 chunking.

## Cost & abuse controls

The live demo answers over a public URL using **one API key — the owner's**. Each question
is a single `claude-sonnet-5` call (~1–3¢; retrieval and embeddings run locally and cost
nothing), so an unthrottled public URL is a standing bill risk if someone scripts it. Two
layers guard against that.

**App-side guardrails** (configurable via env / `st.secrets`):

| Setting | Default | Effect |
|---|---|---|
| `RATE_LIMIT_PER_HOUR` | `60` | Hard cap on Claude calls per rolling hour across *all* users of the running app. Over the limit the app shows "demo is busy" and makes no call — the real spend bound on a single-container deploy. |
| `MAX_MESSAGES_PER_SESSION` | `20` | Per-browser-session question cap (politeness — a new tab resets it). |
| `MAX_QUESTION_CHARS` | `600` | Longer questions are rejected inline, before any API call. |
| `HISTORY_TURNS` | `3` | Only the last N turns are sent to the API, so a long chat doesn't inflate every request. |
| `MAX_TOKENS` | `768` | Caps output tokens (≈ output cost) per answer. |
| `APP_PASSWORD` | _(unset)_ | When set, the app requires this shared password before showing the uploader or chat — removes drive-by abuse. |

**Account backstop** (set up once in the [Anthropic Console](https://console.anthropic.com)):

1. Create a **Workspace** for this app and mint an API key scoped to it — it can be
   revoked or capped in isolation. Use that key as the Streamlit secret.
2. Set a **monthly spend limit** on the Workspace ($10–25 is plenty for a demo). When it
   is reached the key errors and the app stops answering — the bill cannot exceed it.
3. Turn on **usage alert emails** (e.g. 50% and 90%).

Also consider restricting the app's viewers under Streamlit **Settings → Sharing** if it
doesn't need to be fully public.

## Deploy

Free hosting on **Streamlit Community Cloud**:

1. ✅ Push this repo to **public GitHub** — done: [Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot).
2. Set up the API-key backstop first — see [Cost & abuse controls](#cost--abuse-controls):
   a dedicated Anthropic **Workspace**, a scoped key, a monthly spend limit, and alert
   emails.
3. At [share.streamlit.io](https://share.streamlit.io) → **New app** → pick the
   repo/branch, set **main file** to `app.py`.
4. **Advanced settings** → Python **3.12** (matches `.python-version`).
5. **Secrets** → paste (see `.streamlit/secrets.toml.example`):
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."   # the Workspace-scoped key
   # optional guardrail overrides:
   # APP_PASSWORD = "share-this-with-reviewers"
   # RATE_LIMIT_PER_HOUR = "60"
   ```
6. **Deploy.** First load takes ~1–2 min while the MiniLM model downloads;
   `data/samples/` is indexed automatically on the first run.
7. Copy the app URL into the **Live demo** line at the top of this README.

Notes:

- The container disk is **ephemeral** — uploaded files and their index reset on
  every reboot; the committed `data/samples/` always reload, so the demo is
  never empty.
- If the build fails with `unsupported version of sqlite3`, uncomment
  `pysqlite3-binary` in `requirements.txt` and add this shim as the first lines
  of `app.py`:
  ```python
  __import__("pysqlite3")
  import sys; sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
  ```

## Deployment log (this instance)

Concrete record of what's actually configured for the live deployment above —
so a future change (rotating the key, raising the cap, opening access) starts
from what's true today instead of guesswork. Update this section whenever a
setting below changes.

**GitHub**
- Repo: [Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot), public, branch `main`
- Commits authored as `Iblis-Code <275904533+Iblis-Code@users.noreply.github.com>`
  (set via `git config --global user.name` / `user.email` — real email kept out of
  commit history on purpose)
- `gh` CLI is authenticated as `Iblis-Code` locally (`gh auth status` to confirm/renew)

**Anthropic Console** — [platform.claude.com/settings/workspaces](https://platform.claude.com/settings/workspaces)
- Dedicated workspace: **`rag-chatbot-demo`** (kept separate from any other API usage on
  this account, so it can be capped/revoked in isolation)
- API key minted *inside* that workspace and used as the `ANTHROPIC_API_KEY` Streamlit
  secret (the raw key value isn't recorded anywhere in this repo or README, by design —
  if it's lost, revoke it in the Console and mint a new one, then update the Streamlit
  secret)
- Started from **$5 of organizational credit**, explicitly framed as a temporary
  prove-it-out budget, not a production allocation
- Workspace **Limits** tab (workspace details page → **Limits**): a monthly spend cap
  set below the $5 credit (leaving a small buffer), plus email usage-alert
  notification(s) via **Add notification** so a threshold email arrives before the
  hard cap is hit. Exact dollar values were set interactively in the Console UI, not
  tracked here — check/adjust them on that tab directly; they're the first thing to
  raise if the $5 credit is upgraded later.

**Streamlit Community Cloud** — [share.streamlit.io](https://share.streamlit.io)
- App URL: **https://rag-chatbot-project-1.streamlit.app/**
- Source: `Iblis-Code/rag-chatbot`, branch `main`, main file `app.py`
- Python version: **3.12** (matches `.python-version`; deliberately not the 3.14
  default Streamlit offered, to avoid torch/chromadb wheel issues on a brand-new
  Python)
- Secrets configured (Settings → Secrets): `ANTHROPIC_API_KEY` (the `rag-chatbot-demo`
  key above) and `APP_PASSWORD` (a shared password chosen at deploy time — share it
  out-of-band with anyone you want to try the app; rotate by editing the same secret)
- **Viewer access: restricted**, not public — Settings → Sharing is set to specific
  allowed viewers rather than "anyone with the link." This was a deliberate choice
  while proving things out on the $5 credit (belt-and-suspenders alongside
  `APP_PASSWORD` and the app's rate limits). **To open it up:** Streamlit app →
  Settings → Sharing → switch to public/anyone-with-the-link. Nothing else needs to
  change — `APP_PASSWORD` and the app-side guardrails (`RATE_LIMIT_PER_HOUR`, etc.,
  see [Cost & abuse controls](#cost--abuse-controls)) still apply after that switch.
- No `pysqlite3-binary` shim was needed — the build succeeded against ChromaDB as-is
  on Streamlit's current base image. If a future redeploy hits
  `unsupported version of sqlite3`, see the fallback in [Deploy](#deploy) above.

**What's *not* recorded here on purpose:** the actual API key and `APP_PASSWORD`
values, and the exact spend-limit/alert dollar amounts — all live only in the
Anthropic Console and Streamlit secrets, never in this repo.

## Configuration

All settings resolve as: real env var / `.env` → `st.secrets` (on Streamlit) →
default below.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(required)_ | Claude API key |
| `CLAUDE_MODEL` | `claude-sonnet-5` | generation model |
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | local embedding model |
| `CHROMA_DIR` | `./chroma_db` | vector store directory (resolved under repo root) |
| `COLLECTION_NAME` | `documents` | Chroma collection name |
| `CHUNK_SIZE` | `800` | max characters per chunk (excluding overlap) |
| `CHUNK_OVERLAP` | `150` | characters of the previous chunk prepended |
| `TOP_K` | `4` | chunks retrieved per question |
| `MAX_TOKENS` | `768` | max output tokens per answer |
| `HISTORY_TURNS` | `3` | prior turns sent to the API per question |
| `RATE_LIMIT_PER_HOUR` | `60` | app-wide Claude calls allowed per rolling hour |
| `MAX_MESSAGES_PER_SESSION` | `20` | per-session question cap |
| `MAX_QUESTION_CHARS` | `600` | questions longer than this are rejected before any API call |
| `APP_PASSWORD` | _(unset)_ | if set, the UI requires this shared password |

`MAX_TOKENS` and the five rows below it are the cost-control guardrails — see
[Cost & abuse controls](#cost--abuse-controls).

## Development

```powershell
# Full suite. The pipeline is tested with deterministic test doubles, so most
# tests need neither torch nor an API key.
.\.venv\Scripts\python.exe -m pytest -q

# Just the chunker, verbose
.\.venv\Scripts\python.exe -m pytest tests/test_chunker.py -v
```

`requirements-dev.txt` installs everything, but the suite only needs
`pytest python-dotenv pypdf chromadb streamlit` (no torch) — tests that need a
missing optional dep skip themselves.

## Roadmap (Phase 2)

- `PineconeVectorStore` behind a `VECTOR_BACKEND` flag (same interface)
- Optional Voyage AI embeddings behind `EMBED_BACKEND`
- Inline citation rendering, longer conversation memory, chunk-size tuning from the eval
- Dockerfile + CI (pytest + ruff)
