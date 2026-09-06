# RAG Chatbot — Chat with your documents

Ask questions and get answers grounded in **your own documents**, not the model's
training data. Documents are chunked, embedded, and stored in a vector database;
at query time the most relevant chunks are retrieved and passed to Claude, which
answers using only that context and cites the source file for each fact.

Retrieval is hand-written — no LangChain or LlamaIndex — so every step of the pipeline
is visible and testable.

**Live demo:** [rag-chatbot-project-1.streamlit.app](https://rag-chatbot-project-1.streamlit.app/)
— ⚠️ **viewer access is currently restricted** to specific Streamlit accounts while the app
runs on a $5 workspace credit, so a bare link won't open it yet. Opening it up is one switch
(Settings → Sharing); the app-side guardrails below were built for exactly that.

<!-- Screenshot pending -- see "Known limitations". Uncomment once the PNG exists, so
     GitHub doesn't render a broken-image icon in the meantime.
![The chat UI, showing a grounded answer and its Sources panel](docs/images/screenshot.png)
-->

## Status

| Part | State |
|---|---|
| Config, loaders, chunker, embeddings, vector store, ingest, chatbot | ✅ implemented + unit tested |
| Streamlit UI (`app.py`) | ✅ implemented + smoke tested (`AppTest`) |
| CLI scripts (`scripts/ingest_cli.py`, `scripts/eval_retrieval.py`) | ✅ implemented + tested |
| Test suite | ✅ `pytest`, **63/63 passing** |
| Sample documents + `tests/eval_set.json` | ✅ 3 demo docs, 11-question eval set (**hit@4 = 1.00, MRR = 1.00**) |
| GitHub repo | ✅ public — [Iblis-Code/rag-chatbot](https://github.com/Iblis-Code/rag-chatbot), branch `main` |
| Anthropic Workspace + key | ✅ `rag-chatbot-demo` workspace, scoped key, spend limit + usage alerts |
| Streamlit Cloud deploy | ✅ live — Python 3.12, `APP_PASSWORD` set. Viewer access deliberately **restricted** while proving things out on the $5 credit; flipping it to public is a one-click change in Settings → Sharing. |
| Cost & abuse controls | ✅ rate limits, history cap, input cap, password gate — see [docs/CONFIGURATION.md](docs/CONFIGURATION.md) |

## Docs

- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** — every environment variable, the cost
  guardrails, and the design tradeoffs behind them.
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — how to deploy it, and the concrete record of
  what is configured for the live instance.
- **[docs/PLAN.md](docs/PLAN.md)** — the original build plan, kept as a historical record.

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
  changes). Chunk IDs are `sha1(doc_key:page:index)`, where `doc_key` is the file's
  path rather than its bare name, so same-named files in different folders don't
  collide. Re-ingesting a file deletes its previous chunks before writing the new
  ones, so editing a document down doesn't leave stale text behind.
- **Generation** (`rag/chatbot.py`) — Claude via the official `anthropic` SDK,
  streamed. Retrieval happens eagerly (sources shown immediately); the token
  stream is lazy. If nothing relevant is retrieved, it says so instead of guessing.

## Project layout

```
project-1/
├── app.py                     # Streamlit UI (entry point)
├── rag/
│   ├── config.py              # env vars + constants (single source of truth)
│   ├── loaders.py             # pdf/txt/md -> list[Document]
│   ├── chunker.py             # text -> overlapping chunks
│   ├── embeddings.py          # sentence-transformers singleton
│   ├── vector_store.py        # VectorStore ABC + ChromaVectorStore
│   ├── ingest.py              # load -> chunk -> embed -> store
│   └── chatbot.py             # retrieve -> prompt -> stream answer + sources
├── scripts/
│   ├── ingest_cli.py          # python -m scripts.ingest_cli data/samples
│   └── eval_retrieval.py      # hit@k + MRR over a small Q->source set
├── data/samples/              # committed demo docs, auto-indexed on first run
├── tests/                     # 63 tests
│   ├── conftest.py            #   isolates ChromaDB to a temp dir per test
│   ├── helpers.py             #   test doubles (deterministic embedder, in-mem store)
│   ├── eval_set.json          #   11 question -> expected-source pairs
│   └── test_*.py              #   chunker, loaders, ingest, chatbot, scripts, app, smoke
├── .streamlit/
│   ├── config.toml            # light theme, 25 MB upload cap
│   └── secrets.toml.example   # secret format for local / Streamlit Cloud
├── .env.example
├── .python-version            # 3.12, the Streamlit Cloud target
├── requirements.txt           # runtime deps
├── requirements-dev.txt       # runtime + pytest
└── docs/                      # CONFIGURATION.md, DEPLOYMENT.md, PLAN.md
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt   # runtime + pytest; includes torch via sentence-transformers
Copy-Item .env.example .env           # then add your ANTHROPIC_API_KEY
```

Developed on Python 3.14; deployed on 3.12, which is what `.python-version` pins for
Streamlit Cloud. Anything from 3.11 up should work. The first embedding call downloads the
~90 MB MiniLM model and caches it locally.

## Run

```powershell
streamlit run app.py
```

Then, in the browser:

1. On first launch the app indexes any files in `data/samples/` so there is
   something to ask about immediately. The sidebar shows the chunk count.
2. Add your own PDF / TXT / Markdown files with the sidebar uploader and click
   **Ingest uploaded files**; re-ingesting the same file replaces its previous chunks.
3. Ask questions in the chat box. Each answer streams in and is followed by a
   **Sources** panel listing the chunks it was grounded in. Questions with no
   relevant match get an "I don't know" instead of a guess.
4. **Clear index** empties the vector store; **Reset chat** clears the transcript.

Without `ANTHROPIC_API_KEY` set, indexing still works but the chat box is disabled.

## Command line

```powershell
# Index files/directories into the persistent store (--reset to start fresh)
python -m scripts.ingest_cli data/samples
python -m scripts.ingest_cli --reset docs/ notes.md

# Retrieval quality: hit@k + MRR over tests/eval_set.json
python -m scripts.eval_retrieval --k 4
python -m scripts.eval_retrieval --min-hit-rate 0.8   # non-zero exit if below (CI hook)
```

`eval_retrieval` needs the store populated (run `ingest_cli` first) and an eval set at
`tests/eval_set.json` — a JSON list of `{"question": "...", "expected_source": "file.md"}`
items (`expected_sources` list also accepted). Use it to tune `CHUNK_SIZE` /
`CHUNK_OVERLAP` / `TOP_K` against a measurement instead of by feel.

On the bundled sample docs this scores **hit@4 = 1.00, MRR = 1.00** (11/11 questions
retrieve the correct document first), with `all-MiniLM-L6-v2` and the default 800/150
chunking.

## Development

```powershell
# Full suite. The pipeline is tested with deterministic test doubles, so most
# tests need neither torch nor an API key.
.\.venv\Scripts\python.exe -m pytest -q

# Just the chunker, verbose
.\.venv\Scripts\python.exe -m pytest tests/test_chunker.py -v
```

`requirements-dev.txt` installs everything, but the suite only needs
`pytest python-dotenv pypdf chromadb streamlit` — no torch, no network, no API key. Every
test that would otherwise hit the embedding model uses a deterministic hashing double
(`tests/helpers.py`), so the whole suite runs in seconds and is reproducible offline. Tests
that need a missing optional dependency skip themselves.

## Known limitations

Deliberate scope boundaries for a demo, written down rather than left as surprises.

**Uploaded documents are shared between visitors.** The app keeps one Chroma collection per
server process, so anything you upload through the sidebar is retrievable by anyone else
using the same instance, and **Clear index** empties it for everyone — including the bundled
samples until the next restart. Don't upload anything confidential. Per-visitor isolation is
the first Phase 2 item.

**Uploads are trusted.** An uploaded file's name is used directly as the path it's written to
under `data/uploads/`, without sanitizing. The container disk is ephemeral and the app is
access-restricted, so the blast radius is small, but it should be sanitized before the demo
is opened to the public.

**Errors are surfaced verbatim.** A failure during retrieval or generation is rendered into
the chat as `ExceptionType: message`. Good for debugging a demo, too chatty for production.

**No CI.** Tests, lint, and the `eval_retrieval --min-hit-rate` gate all exist and are wired
to run, but nothing runs them automatically on push.

**No screenshot yet**, and the live demo is viewer-restricted — so right now neither route
lets a reviewer see the app running. Fixing either one closes the gap; opening viewer access
is the better fix, since the guardrails were designed for it.

**No LICENSE**, which by default means all rights reserved. Undecided rather than intentional.

## Roadmap (Phase 2)

- `PineconeVectorStore` behind a `VECTOR_BACKEND` flag (same interface, no call-site changes)
- Optional Voyage AI embeddings behind `EMBED_BACKEND`
- Per-visitor document isolation — uploads currently share one collection across all users
- Inline citation rendering, longer conversation memory, chunk-size tuning from the eval
- Dockerfile + CI (pytest + ruff + the `eval_retrieval --min-hit-rate` gate)
