# Configuration

Every setting resolves in one order, implemented in [`rag/config.py`](../rag/config.py):

1. a real environment variable (including anything loaded from a local `.env`);
2. `st.secrets[KEY]` — only when the app is already running under Streamlit, so plain
   CLI use never imports Streamlit;
3. the default below.

`rag/config.py` is the authoritative source; this page explains what each value is *for*.
Values are validated at import time, so a bad number fails fast with a clear message
rather than misbehaving later.

Copy-paste templates live in [`.env.example`](../.env.example) (local) and
[`.streamlit/secrets.toml.example`](../.streamlit/secrets.toml.example) (Streamlit Cloud).

## Core settings

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(required)_ | Claude API key. Without it, indexing still works but the chat input is disabled. |
| `CLAUDE_MODEL` | `claude-sonnet-5` | Generation model. `claude-opus-5` is the higher-quality, higher-cost alternative. |
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model, 384-dim. Runs on your machine — no second API key, no per-query cost. |
| `CHROMA_DIR` | `./chroma_db` | Vector store directory. Relative paths resolve under the repo root. |
| `COLLECTION_NAME` | `documents` | Chroma collection name. |
| `CHUNK_SIZE` | `800` | Max characters per chunk, excluding the overlap prefix. |
| `CHUNK_OVERLAP` | `150` | Characters of the previous chunk prepended to each following chunk, so context survives a boundary. Must be smaller than `CHUNK_SIZE`. |
| `TOP_K` | `4` | Chunks retrieved per question and passed to the model as context. |

Use `python -m scripts.eval_retrieval` to tune `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K`
against a real measurement rather than by feel.

## Cost and abuse guardrails

The live demo answers over a public URL on **one API key — the owner's**. Each question is a
single `claude-sonnet-5` call (retrieval and embeddings run locally and cost nothing), so an
unthrottled public URL is a standing bill risk if someone scripts it. These bound the blast
radius; the hard backstop is the workspace spend limit described in
[DEPLOYMENT.md](DEPLOYMENT.md).

| Variable | Default | Effect |
|---|---|---|
| `RATE_LIMIT_PER_HOUR` | `60` | Hard cap on Claude calls per rolling hour across *all* users of the running app. Over the limit the app shows "demo is busy" and makes no call. On a single-container deploy this is the real spend bound. **The live deployment overrides this to 20** — see the note below. |
| `MAX_MESSAGES_PER_SESSION` | `20` | Per-browser-session question cap. Politeness only — a new tab resets it. |
| `MAX_QUESTION_CHARS` | `600` | Longer questions are rejected inline, before any API call. |
| `HISTORY_TURNS` | `3` | Only the last N turns are sent to the API, so a long chat doesn't inflate every request. |
| `MAX_TOKENS` | `768` | Caps output tokens, and so output cost, per answer. |
| `APP_PASSWORD` | _(unset)_ | When set, the app requires this shared password before showing the uploader or chat. Unset on the live deployment, which is open to anyone with the link. |

### Why the live deployment uses 20, not 60

With no password gate, `RATE_LIMIT_PER_HOUR` and the workspace spend cap are the only things
between the demo and a scripted client. A question costs roughly **0.6¢ typical, 1.1¢ worst
case** (~1,600 input tokens against up to 768 output, at Sonnet 5's $2/$10 per MTok), so a $5
credit buys somewhere between **450 and 870 questions**.

At 60/hour, sustained abuse exhausts that in 8–15 hours; at 20/hour it takes three times as
long. Genuine reviewer traffic is nowhere near either number, so the lower cap costs real
users nothing. The failure mode being bought off here isn't an unexpected bill — the spend cap
already prevents that — it's the demo going dark mid-job-search and staying dark until the
credit is topped up.

The code default stays 60 for local use; production sets 20 as a Streamlit secret.

## Design notes

**Extended thinking is disabled.** `rag/chatbot.py` passes `thinking={"type": "disabled"}`
to the Messages API. On current Claude models thinking is *on* by default when the parameter
is omitted, and thinking tokens are both billed and counted against `MAX_TOKENS`. For grounded
extract-and-cite over four retrieved chunks there is nothing to reason about, so leaving it on
would pay for reasoning nobody sees and risk truncating the answer before it finishes. If you
raise `MAX_TOKENS` substantially and start asking multi-hop questions, this is the first
setting worth revisiting.

**Prompt caching is not used.** The retrieved context differs on every query, so only the
~120-token system prefix is cacheable — below the minimum cacheable prefix, and not worth the
complexity.

**Upload size** is capped at 25 MB by `maxUploadSize` in
[`.streamlit/config.toml`](../.streamlit/config.toml), which also sets the light theme.
