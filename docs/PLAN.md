# Plan: RAG Chatbot ("Chat with your documents")

> **Historical record.** This is the build plan as written before and during
> implementation. Everything in it shipped, and the project is deployed. Where this
> document and the code disagree, **the code wins** — the per-step specs below were not
> rewritten as the implementation evolved (see "Deviations" for the corrections).
>
> For current state, read: [README](../README.md) (what it is and how to run it),
> [CONFIGURATION.md](CONFIGURATION.md) (settings and defaults), and
> [DEPLOYMENT.md](DEPLOYMENT.md) (how it is deployed and what is configured).

## Context

This is the first portfolio project for an AI Engineer portfolio. Goal: a chatbot that
answers questions grounded in a user's own documents (not the LLM's training data), using
a vector database for retrieval and the Claude API for generation. The finished artifact
must be something a hiring reviewer can click: a public GitHub repo plus a live deployed
demo, with a README that explains the RAG architecture.

Decisions locked in during planning:

- **Language:** Python (3.11+).
- **Vector DB:** ChromaDB only for v1, local + persistent. A `VectorStore` interface is
  introduced now so Pinecone can be added in Phase 2 without touching call sites.
- **LLM:** Claude via the official `anthropic` SDK. Default model `claude-sonnet-5`
  (chosen for cost/latency in an interactive demo; configurable to `claude-opus-5` via env).
- **Embeddings:** local `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) — free,
  offline, no second API key.
- **Interface:** Streamlit chat UI.
- **Scope:** runs locally *and* deployed live (Streamlit Community Cloud). Includes a
  README, committed sample documents, `.env` handling, and a light retrieval-quality eval.
- **Cost / abuse controls:** the live demo answers over a public URL on the author's own
  Claude API key, so cost containment is in scope. Two layers: app-level guardrails
  (global + per-session rate limits, conversation history bounded to the last few turns, a
  lower `MAX_TOKENS`, an input-length cap, and an optional shared-password gate) and an
  Anthropic **Workspace** with a hard monthly spend limit + usage alerts as the backstop
  that a bug or a scripted abuser cannot exceed. See step 13.

No framework (LangChain/LlamaIndex) — the RAG steps are hand-written so the repo
demonstrates understanding of the pipeline. Third-party text splitters are avoided for the
same reason.

## Build status (updated 2026-09-02)

| Step | Module | State |
|---|---|---|
| 1 | `rag/config.py` | ✅ done |
| 2 | `rag/loaders.py` | ✅ done (`tests/test_loaders.py`) |
| 3 | `rag/chunker.py` | ✅ done (`tests/test_chunker.py`) |
| 4 | `rag/embeddings.py` | ✅ done (lazy singleton; exercised by smoke test) |
| 5 | `rag/vector_store.py` | ✅ done (`VectorStore` ABC + `ChromaVectorStore`) |
| 6 | `rag/ingest.py` | ✅ done (`tests/test_ingest.py`) |
| 7 | `rag/chatbot.py` | ✅ done (`tests/test_chatbot.py`, faked client) |
| 8 | `app.py` | ✅ done (`tests/test_app.py`, Streamlit `AppTest`) |
| 9 | `scripts/ingest_cli.py`, `scripts/eval_retrieval.py` | ✅ done (`tests/test_scripts.py`); eval reports hit@k **and** MRR |
| 10 | `tests/` | ✅ 60 passing; `tests/helpers.py` holds the torch-free test doubles; `tests/conftest.py` isolates ChromaDB to a temp dir; `tests/test_smoke.py` is a real ChromaDB round-trip |
| 11 | `data/samples/`, `tests/eval_set.json`, README, `.env.example` | ✅ done — 3 fictional Acme docs (handbook / analytics FAQ / security policy) + an 11-question eval set. Real-embedding run: **hit@4 = 1.00, MRR = 1.00** (9 chunks from 3 files). |
| 12 | Deployment | ✅ config done — split `requirements.txt` / `requirements-dev.txt`, `.python-version` (3.12), `.streamlit/secrets.toml.example`, and the deploy walkthrough (now in `docs/DEPLOYMENT.md`) with the sqlite shim fallback. Published and live. |
| 13 | Cost controls & abuse protection — `rag/config.py`, `rag/chatbot.py`, `app.py`, `tests/` | ✅ done (`tests/test_app.py`, `tests/test_chatbot.py`; +7 tests, 60 total). App-side guardrails shipped; the Console spend-limit runbook is a manual deploy step (see step 13). |

Deviations from the plan as written:

- `ingest.py` exposes `ingest_documents` / `ingest_paths` (both accept an injected
  `embed_fn`), and `IngestReport` counts `files` / `documents` / `chunks`.
- `chatbot.py` exposes `answer() -> RagResponse(chunks, stream, sources)` rather than a
  bare `answer_stream`; retrieval is eager, the token stream is lazy. `retrieve()` also
  takes an optional `embed_fn` for torch-free testing.
- Chunk index in the ID restarts per `(source, page)`.
- `app.py` persists each answer's retrieved chunks in `st.session_state` so the
  "Sources" expander survives reruns; the embedding model is warmed lazily on the
  first question, not at startup, so the page loads fast.
- Both scripts split into a testable core (`run_ingest`, `run_eval` / `evaluate` /
  `load_eval_set`) plus a thin `main(argv)` returning an exit code; the core
  functions take an injected `store` / `embed_fn` so the tests run torch-free.
- `eval_retrieval` reports MRR alongside hit@k, records the rank of the first
  expected source per question, and accepts `expected_source` or
  `expected_sources`; `--min-hit-rate` gives a CI gate.
- Runtime vs dev deps are split (`requirements.txt` / `requirements-dev.txt`) so the
  deployed image stays lean. `.python-version` pins 3.12 for Streamlit Cloud (a
  conservative, widely-supported target); local dev on 3.14 works fine (torch 2.13
  installed cleanly).
- Step 13 as built: `chatbot._trim_history(history, max_turns)` does the history
  bounding and keeps the result starting with a `user` message. `app.py` gained
  `require_password()` (`st.stop()` until `APP_PASSWORD` matches), `rate_limit_ok()`
  backed by a module-level `_rate_window()` `@st.cache_resource` deque for the app-wide
  hourly cap, and a per-session question count that disables `st.chat_input`. The
  long-question and rate-limit checks short-circuit before any message is appended to
  `st.session_state`. `+7` tests (3 in `test_chatbot.py`, 4 in `test_app.py`) → 60.

## Where this ended up

**All 13 plan steps are implemented, tested, and deployed.** The four manual, outward-facing
tasks this section used to track as pending were all completed:

1. ✅ Repo pushed to public GitHub — [Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot), branch `main`.
2. ✅ Dedicated Anthropic Workspace `rag-chatbot-demo` created, with a scoped key, a monthly
   spend limit, and usage alerts. Details in [DEPLOYMENT.md](DEPLOYMENT.md).
3. ✅ Deployed on Streamlit Community Cloud (Python 3.12; `APP_PASSWORD` was set at the
   time, and later removed when access was opened up — see below).
4. ✅ Live URL in the README.

Viewer access was restricted while the app proved itself out, then opened: Streamlit sharing
is public, `APP_PASSWORD` was removed (a password prompt would have blocked a reviewer just as
effectively as a sharing wall), and `RATE_LIMIT_PER_HOUR` was lowered to 20 in production to
stretch the credit against scripted traffic. See [DEPLOYMENT.md](DEPLOYMENT.md).

Post-deployment changes not in the original plan:

- **`thinking` is explicitly disabled** on the Messages API call. Omitting the parameter
  leaves adaptive thinking on, whose tokens are billed *and* counted against `MAX_TOKENS`
  (768) — paying for reasoning nobody sees and risking a truncated answer. See
  [CONFIGURATION.md](CONFIGURATION.md) § Design notes.
- **Chunk IDs key on `doc_key`, not `source`.** `source` is the bare filename, so
  `a/notes.md` and `b/notes.md` hashed to identical IDs and silently overwrote each other.
  `Document.doc_key` is the file's path (project-relative when possible); `source` still
  carries the filename for citations.
- **Ingestion deletes before it upserts.** Upsert alone never removes anything, so editing a
  document *down* left its old trailing chunks in the store as retrievable stale text.
  `VectorStore.delete_by_source(doc_key)` is called for each file before its new chunks land.
- **The test suite is genuinely torch-free.** `tests/test_app.py` was still loading the real
  ~90 MB embedding model on each of its seven tests, which made it fail intermittently on a
  cold cache against the 30s `AppTest` timeout. It now uses the same deterministic hashing
  double as the rest of the suite. 60 -> 63 tests, ~40s -> ~10s.
- **Dependencies carry major-version caps** (`anthropic>=1.3,<2`, etc.) so a Streamlit Cloud
  redeploy cannot pull a breaking major without a code change.
- **Retrieval has a relevance threshold** (`MAX_DISTANCE`, 0.75 cosine). Similarity search
  always returns its top-k however poor the match, so grounding was previously enforced only
  by the system prompt: an off-topic question still reached Claude and cost a full API call
  to be refused. `chatbot.is_relevant()` now gates on the nearest chunk. The default was
  measured against the sample docs rather than guessed — answerable questions peak at 0.63,
  off-topic ones bottom out at 0.79. `scripts/eval_retrieval.py` deliberately skips the gate
  so the eval keeps measuring pure ranking. 63 -> 68 tests.
- **`IngestReport.files` counts distinct files, not filenames.** It was counting unique
  `source` values, so ingesting `a/notes.md` and `b/notes.md` together reported "1 file"
  while correctly storing two. The last place `source` was used where `doc_key` was meant;
  the report line still lists display names, which is what `source` is for.
- **Verified, not changed:** `rag/config.py` reads `st.secrets` only when `"streamlit" in
  sys.modules`, which looks like it depends on `app.py`'s import order. It does not — the
  Streamlit CLI has already imported the package before its ScriptRunner `exec`s the app
  script in the same process. The guard is what keeps CLI use from importing Streamlit; the
  reasoning is now recorded in the function's docstring so it isn't re-litigated.

Local environment:

- `.venv/` here has the **full** runtime + dev deps installed (torch 2.13, chromadb,
  sentence-transformers, anthropic 1.x, streamlit). Interpreter is Python 3.14.
- Tests: `.\.venv\Scripts\python.exe -m pytest -q` — 63 passing.
- App: set `ANTHROPIC_API_KEY`, then `.\.venv\Scripts\python.exe -m streamlit run app.py`
- The test suite redirects ChromaDB to a temp dir (`tests/conftest.py`). Running
  `scripts/*` or the app directly creates `./chroma_db/` in the repo (gitignored).

Verified end-to-end: real ingest of `data/samples/` = 9 chunks / 3 files;
`python -m scripts.eval_retrieval` = **hit@4 = 1.00, MRR = 1.00**; `pytest -q` = 68 passing;
a real `streamlit run` boots clean, including with `APP_PASSWORD` and `RATE_LIMIT_PER_HOUR` set.

Orientation: usage → [README](../README.md); settings/defaults → `rag/config.py` and
[CONFIGURATION.md](CONFIGURATION.md); ops → [DEPLOYMENT.md](DEPLOYMENT.md); RAG entry
point → `rag.chatbot.answer()`; torch-free test doubles → `tests/helpers.py`.

## Tech stack / dependencies (`requirements.txt`)

```
anthropic>=1.3,<2
chromadb>=1.5,<2
sentence-transformers>=6.0,<7
pypdf>=6.0,<7
streamlit>=1.63,<2
python-dotenv>=1.2,<2
pytest>=9.0,<10        # dev
```

(Originally written with open lower bounds; major-version caps were added later so a
Streamlit Cloud redeploy can't pull a breaking major on its own.)

Note: `sentence-transformers` pulls in `torch` (CPU wheel is fine). First run downloads
the ~90 MB MiniLM model and caches it.

## Project structure

> Planned layout, kept for historical context. The **current** tree (adds `docs/`,
> `requirements-dev.txt`, `.python-version`, `.streamlit/secrets.toml.example`, and the
> full `tests/` set) is in the README's "Project layout" section.

```
project-1/
├── app.py                     # Streamlit UI (entry point)
├── rag/
│   ├── __init__.py
│   ├── config.py              # env vars + constants (single source of truth)
│   ├── loaders.py             # PDF/txt/md -> list[Document(text, metadata)]
│   ├── chunker.py             # text -> overlapping chunks (unit-tested)
│   ├── embeddings.py          # SentenceTransformer singleton: embed_texts / embed_query
│   ├── vector_store.py        # VectorStore ABC + ChromaVectorStore
│   ├── ingest.py              # load -> chunk -> embed -> store (deterministic IDs / upsert)
│   └── chatbot.py             # retrieve -> build prompt -> stream Claude answer + sources
├── scripts/
│   ├── ingest_cli.py          # python -m scripts.ingest_cli data/samples
│   └── eval_retrieval.py      # hit@k over a small hand-written Q->source set
├── data/
│   └── samples/               # 2-3 small committed markdown docs (demo works on clone)
├── tests/
│   ├── test_chunker.py
│   └── test_smoke.py          # tiny ingest+retrieve round-trip (temp Chroma dir)
├── .streamlit/config.toml     # optional theme
├── .env.example
├── .gitignore                 # .env, chroma_db/, data/uploads/, __pycache__/, .venv/
├── requirements.txt
└── README.md
```

## Implementation steps

> These per-step specs were **not** updated as the code evolved. Steps 7, 9, and 10 in
> particular describe a pre-refactor API. Read "Deviations from the plan as written" above
> for the corrections, or just read the code.

### 1. `rag/config.py`

> Current defaults and their rationale live in [CONFIGURATION.md](CONFIGURATION.md); the
> list below is what was originally specified.
Load `.env` via `python-dotenv`; also fall back to `st.secrets` when running on Streamlit
Cloud (guard the import). Expose: `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` (default
`claude-sonnet-5`), `EMBED_MODEL` (default `sentence-transformers/all-MiniLM-L6-v2`),
`CHROMA_DIR` (default `./chroma_db`), `COLLECTION_NAME` (default `documents`),
`CHUNK_SIZE` (default 800 chars), `CHUNK_OVERLAP` (default 150), `TOP_K` (default 4),
`MAX_TOKENS` (default 768 — lowered from 2048 in step 13 to cap per-answer output cost).

Step 13 adds cost-control settings, all resolved through the same env → `st.secrets` →
default chain: `HISTORY_TURNS` (default 3), `MAX_QUESTION_CHARS` (default 600),
`MAX_MESSAGES_PER_SESSION` (default 20), `RATE_LIMIT_PER_HOUR` (default 20, originally 60),
`APP_PASSWORD` (default unset — when set, the UI requires it before any Claude call).

### 2. `rag/loaders.py`
`Document` dataclass: `text: str`, `metadata: dict` (`source` filename, `page` for PDFs).
`load_document(path) -> list[Document]`:
- `.pdf` -> `pypdf.PdfReader`, one `Document` per page (page number kept for future citations).
- `.txt` / `.md` -> single `Document`.
- Unknown extension -> raise a clear `ValueError`.
`load_paths(paths) -> list[Document]` expands directories.

### 3. `rag/chunker.py`
`chunk_text(text, size, overlap) -> list[str]`: split on blank-line paragraph boundaries,
greedily pack paragraphs up to `size`, hard-split any oversized paragraph, and prepend the
last `overlap` characters of the previous chunk to preserve context across boundaries.
Strip whitespace; drop empty chunks. This is the main unit-tested piece.

### 4. `rag/embeddings.py`
Module-level lazy singleton `SentenceTransformer(config.EMBED_MODEL)`.
`embed_texts(list[str]) -> list[list[float]]` (batched, `normalize_embeddings=True`),
`embed_query(str) -> list[float]`. Normalized vectors + cosine space.

### 5. `rag/vector_store.py`
`VectorStore` ABC: `add(ids, embeddings, documents, metadatas)`, `query(embedding, top_k)
-> list[Retrieved]` (`Retrieved` = text + metadata + distance), `count()`, `reset()`.
`ChromaVectorStore`: `chromadb.PersistentClient(path=config.CHROMA_DIR)` +
`get_or_create_collection(config.COLLECTION_NAME, metadata={"hnsw:space": "cosine"})`.
Phase 2 adds `PineconeVectorStore` implementing the same ABC.

### 6. `rag/ingest.py`
`ingest_paths(paths, store) -> IngestReport`: for each `Document` -> `chunk_text` -> embed
all chunks -> `store.add`. Chunk ID = `sha1(f"{source}:{page}:{chunk_index}")` so
re-ingesting the same file upserts instead of duplicating. Return counts (files, chunks).

### 7. `rag/chatbot.py`
- `retrieve(question, store, top_k) -> list[Retrieved]`: `embed_query` -> `store.query`.
- `build_messages(question, chunks, history)`: system prompt =
  *"Answer using only the provided context from the user's documents. If the answer is not
  in the context, say you don't know. Cite the source filename in square brackets after
  the facts it supports. Be concise."* User content = numbered context blocks
  (`[source] <chunk text>`) followed by the question. Include prior turns from `history`.
- `answer_stream(question, store, history) -> Iterator[str]`: uses
  `client.messages.stream(model=config.CLAUDE_MODEL, max_tokens=config.MAX_TOKENS,
  system=..., messages=...)` and yields `stream.text_stream` deltas. Also returns the
  retrieved `chunks` so the UI can show sources. If retrieval is empty, short-circuit with
  a "no documents indexed / nothing relevant found" message.
- Create the `anthropic.Anthropic()` client once at module level (reads `ANTHROPIC_API_KEY`).

### 8. `app.py` (Streamlit)
- `@st.cache_resource` for the embedder and the `ChromaVectorStore` (built once per session).
- Sidebar: `st.file_uploader` (multiple, pdf/txt/md) -> save to `data/uploads/` -> "Ingest"
  button runs `ingest_paths` and reports chunk count; "Clear index" calls `store.reset()`;
  show `store.count()` as "N chunks indexed".
- Main pane: `st.session_state.messages` history rendered with `st.chat_message`;
  `st.chat_input` for the question; stream the answer with `st.write_stream(answer_stream(...))`;
  render retrieved sources in an `st.expander("Sources")` beneath the answer.
- On startup, if `store.count() == 0`, auto-ingest `data/samples/` so the deployed demo and
  a fresh clone both work with zero setup.

### 9. `scripts/`
- `ingest_cli.py`: `python -m scripts.ingest_cli <path...>` -> build store, `ingest_paths`,
  print report. For local/CLI use and for pre-building the index.
- `eval_retrieval.py`: load `tests/eval_set.json` (8-10 `{question, expected_source}`
  pairs written against the sample docs), run `retrieve` for each, print **hit@k**
  (fraction where `expected_source` appears in the top-k). Used to sanity-check and to
  tune `CHUNK_SIZE` / `TOP_K`.

### 10. `tests/`
- `test_chunker.py`: respects `size`, applies `overlap`, loses no source text, handles
  empty / single-paragraph / oversized-paragraph inputs.
- `test_smoke.py`: ingest one in-memory doc into a `tmp_path` Chroma dir, retrieve a known
  phrase, assert the right chunk comes back. Marked slow (needs the embedding model);
  skip cleanly if the model can't be downloaded offline.

### 11. Docs & sample data
- `data/samples/`: 2-3 short synthetic markdown docs (e.g. a fake product FAQ, a small
  "company handbook", a policy doc) — enough variety for real retrieval, small enough to
  commit.
- `README.md`: one-paragraph pitch, live demo URL + screenshot, "How it works" section
  (ingest -> chunk -> embed -> store -> retrieve -> augment prompt -> generate) with a
  text diagram, local setup steps, env vars table, eval results (hit@k number), and a
  "Phase 2 / roadmap" list.
- `.env.example`: `ANTHROPIC_API_KEY=`, plus the optional overrides with their defaults.

### 12. Deployment (Streamlit Community Cloud)
- Push the repo to public GitHub (`gh repo create` or the web UI).
- Create a Streamlit Cloud app pointed at `app.py`; add `ANTHROPIC_API_KEY` under
  **Settings -> Secrets** (read via the `st.secrets` fallback in `config.py`).
- Chroma's on-disk dir is ephemeral on Streamlit Cloud (resets on reboot) — the
  auto-ingest-if-empty step in `app.py` rebuilds the sample index on cold start, so no
  committed DB is needed.
- Put the resulting public URL + a screenshot in the README.

### 13. Cost controls & abuse protection

The deployed demo answers over a public URL on the author's own Claude API key
(`claude-sonnet-5`, ~1–3¢ per question; embeddings are local and free). Unthrottled, a
scripted client on the single Streamlit container is tens of dollars per hour. Two layers.

**App-side guardrails (code — this repo):**

- `rag/config.py`: add `HISTORY_TURNS` (3), `MAX_QUESTION_CHARS` (600),
  `MAX_MESSAGES_PER_SESSION` (20), `RATE_LIMIT_PER_HOUR` (60; later lowered to 20), `APP_PASSWORD` (unset), and
  lower the `MAX_TOKENS` default 2048 → 768. Same `_get` / `_get_int` resolution as the
  rest of config; `_get_int` validation extended to reject `< 1` for the new counters.
- `rag/chatbot.py`: `build_messages` / `answer` trim `history` to the last `HISTORY_TURNS`
  turns before the request, so a long chat doesn't grow every call's input.
- `app.py`:
  - If `APP_PASSWORD` is set, render a password prompt and `st.stop()` until it matches
    (pass/fail in `st.session_state`); no uploader or chat input renders until then.
  - Reject a question longer than `MAX_QUESTION_CHARS` with an inline error and no API call.
  - Per-session counter in `st.session_state`: at `MAX_MESSAGES_PER_SESSION`, disable the
    chat input with a "demo limit reached" caption.
  - Global rolling-window limiter in an `@st.cache_resource` object shared across all
    sessions in the one process — a deque of call timestamps for the last hour; at
    `RATE_LIMIT_PER_HOUR` show "the shared demo is busy, try again later" and skip the
    call. This is the limit that actually bounds spend on a single-container deploy; the
    per-session cap is only politeness (a new tab resets it).
- `.env.example` / `.streamlit/secrets.toml.example`: document the new vars (commented,
  with defaults).
- `tests/`: `MAX_QUESTION_CHARS` rejection path, `HISTORY_TURNS` trimming in
  `build_messages`, the global limiter returning "busy" at the threshold, and the password
  gate blocking `chat_input` (extend `tests/test_app.py` `AppTest`). All torch-free / no
  API key, consistent with the existing suite.

**Ops backstop (Anthropic Console — deploy runbook, not code).** What was actually
configured is recorded in [DEPLOYMENT.md](DEPLOYMENT.md):

- Create a dedicated **Workspace** for this app; mint an API key scoped to it so it can be
  revoked or capped without touching anything else. That scoped key is the
  `ANTHROPIC_API_KEY` Streamlit secret.
- Set a **monthly spend limit** on the Workspace. When it is hit the key
  errors and the app stops answering — the bill cannot exceed it.
- Enable **usage alert emails** (e.g. at 50% and 90%).
- Streamlit Community Cloud: set app visibility / a viewer allowlist under **Settings →
  Sharing** if the demo needn't be fully open; otherwise rely on the guardrails above.
  (As shipped: opened to the public, relying on the guardrails.)
- Prompt caching is *not* used — the retrieved context differs on every query, so only the
  ~120-token system prefix is cacheable; not worth the complexity.

Deployment (step 12) was gated on the Workspace spend limit being in place first. It is
now; see [DEPLOYMENT.md](DEPLOYMENT.md) for what was actually configured.

## Phase 2 (not built; the live list is the README's Roadmap)

- `PineconeVectorStore` behind a `VECTOR_BACKEND=chroma|pinecone` env flag (same
  `VectorStore` ABC, no call-site changes).
- Optional Voyage AI embeddings behind `EMBED_BACKEND`.
- Inline source-citation rendering, longer conversation memory, chunk/overlap tuning
  driven by the eval script, `Dockerfile`, and CI (pytest + ruff).

## Verification

Run from the project root (PowerShell):

1. `python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt`
2. `Copy-Item .env.example .env` then put a real `ANTHROPIC_API_KEY` in `.env`.
3. `python -m scripts.ingest_cli data/samples` -> prints `Ingested 9 chunks from 3 file(s)`.
4. `python -m scripts.eval_retrieval` -> prints `hit@4 = 1.00, MRR = 1.00` on the samples
   (expect >= 0.8; if lower, adjust `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K`).
5. `streamlit run app.py`:
   - Ask a question answerable from the samples -> answer streams in, "Sources" expander
     lists the right file(s).
   - Ask an unrelated question -> the bot says it doesn't know (grounding check).
   - Upload a new PDF in the sidebar, click Ingest, ask about it -> answered.
6. `pytest -q` -> chunker tests pass; smoke test passes (or skips cleanly offline).
7. Cost controls (step 13): set `APP_PASSWORD` and `RATE_LIMIT_PER_HOUR=2` locally and
   `streamlit run app.py` — the password gate blocks the chat until entered; a 3rd
   question within the hour is refused with the "busy" notice; a >600-char question is
   rejected with no API call.
8. Deploy: confirm the Anthropic Workspace has a monthly spend limit + alerts, then push
   to GitHub, create the Streamlit Cloud app, set the scoped `ANTHROPIC_API_KEY` secret
   (plus `APP_PASSWORD` if used), open the public URL, confirm it cold-starts and
   auto-ingests the samples, and run one Q&A end-to-end.
