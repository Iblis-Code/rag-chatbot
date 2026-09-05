"""Measure retrieval quality with hit@k over a small labelled set (plan step 9).

The eval set is a JSON list of items, each with a question and its expected
source file:

    [
      {"question": "How many vacation days do I get?", "expected_source": "handbook.md"},
      {"question": "Who approves expenses?", "expected_sources": ["handbook.md", "policy.md"]}
    ]

``expected_source`` (string) and ``expected_sources`` (list) are both accepted.
A question counts as a hit when any expected source appears in the top-k results.

    python -m scripts.eval_retrieval
    python -m scripts.eval_retrieval --k 3 --min-hit-rate 0.8

Run ``scripts.ingest_cli`` first so there is something to retrieve from.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from rag import config
from rag.chatbot import EmbedQueryFn, retrieve
from rag.loaders import PathLike
from rag.vector_store import ChromaVectorStore, VectorStore

DEFAULT_EVAL_SET = config.PROJECT_ROOT / "tests" / "eval_set.json"


@dataclass
class EvalRow:
    question: str
    expected: list[str]
    retrieved: list[str]
    rank: int | None  # 1-based rank of the first expected source, else None

    @property
    def hit(self) -> bool:
        return self.rank is not None

    @property
    def reciprocal_rank(self) -> float:
        return 1.0 / self.rank if self.rank else 0.0


@dataclass
class EvalResult:
    k: int
    rows: list[EvalRow] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def hits(self) -> int:
        return sum(row.hit for row in self.rows)

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.rows else 0.0

    @property
    def mrr(self) -> float:
        if not self.rows:
            return 0.0
        return sum(row.reciprocal_rank for row in self.rows) / self.total


def load_eval_set(path: PathLike) -> list[dict]:
    """Parse and validate an eval-set JSON file into ``{question, expected}`` items."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Eval set not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} must contain a non-empty JSON list.")

    items: list[dict] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or not item.get("question"):
            raise ValueError(f"item {i}: missing a 'question' field.")
        expected = item.get("expected_sources") or (
            [item["expected_source"]] if item.get("expected_source") else []
        )
        if not expected:
            raise ValueError(
                f"item {i}: needs 'expected_source' or 'expected_sources'."
            )
        items.append(
            {"question": str(item["question"]), "expected": [str(s) for s in expected]}
        )
    return items


def evaluate(
    eval_set: Sequence[dict],
    store: VectorStore,
    k: int,
    embed_fn: EmbedQueryFn | None = None,
) -> EvalResult:
    result = EvalResult(k=k)
    for item in eval_set:
        hits = retrieve(item["question"], store, top_k=k, embed_fn=embed_fn)
        retrieved = [hit.source for hit in hits]
        rank = next(
            (i for i, src in enumerate(retrieved, start=1) if src in item["expected"]),
            None,
        )
        result.rows.append(EvalRow(item["question"], item["expected"], retrieved, rank))
    return result


def format_report(result: EvalResult) -> str:
    lines = [f"{'hit':>4}  {'rank':>4}  question"]
    for row in result.rows:
        mark = "ok" if row.hit else "MISS"
        rank = str(row.rank) if row.rank else "-"
        question = row.question if len(row.question) <= 64 else row.question[:61] + "..."
        lines.append(f"{mark:>4}  {rank:>4}  {question}")
    lines.append("")
    lines.append(
        f"hit@{result.k} = {result.hit_rate:.2f}  ({result.hits}/{result.total})"
        f"   MRR = {result.mrr:.2f}"
    )
    return "\n".join(lines)


def run_eval(
    eval_set_path: PathLike,
    *,
    k: int,
    store: VectorStore,
    embed_fn: EmbedQueryFn | None = None,
) -> EvalResult:
    return evaluate(load_eval_set(eval_set_path), store, k, embed_fn)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.eval_retrieval",
        description="Report hit@k and MRR for retrieval over an eval set.",
    )
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--k", type=int, default=config.TOP_K)
    parser.add_argument(
        "--min-hit-rate",
        type=float,
        default=0.0,
        help="Exit non-zero if hit@k is below this value (for CI).",
    )
    args = parser.parse_args(argv)

    store = ChromaVectorStore()
    if store.count() == 0:
        print(
            "error: the vector store is empty. Run "
            "'python -m scripts.ingest_cli data/samples' first.",
            file=sys.stderr,
        )
        return 2

    try:
        result = run_eval(args.eval_set, k=args.k, store=store)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(format_report(result))
    return 0 if result.hit_rate >= args.min_hit_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
