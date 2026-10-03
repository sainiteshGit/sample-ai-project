"""Live RAG eval demo: real embeddings retrieval, real generation, real judge.

    .venv/bin/python rag_eval_demo.py --k 2

One embeddings call per chunk (cached) plus one per query, one generation
call, and one judge call per query. Requires AZURE_OPENAI_EMBEDDING_DEPLOYMENT
(or OPENAI_EMBEDDING_MODEL) in .env, in addition to the existing chat model.
Retrieval ranks chunks by real cosine similarity between query and chunk
embedding vectors -- this is genuine vector-search RAG, not a keyword stand-in.
"""

import argparse
import math
import os
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, ValidationError

from live_eval_demo import make_client


# ---------------------------------------------------------------------------
# Corpus: deliberately split so some facts live in separate chunks. This
# mirrors a real over-chunked or awkwardly-split knowledge base.
# ---------------------------------------------------------------------------

CORPUS = {
    "refund_days": "Refunds are allowed within 30 days of purchase.",
    "refund_condition": "The item must be unused and in original packaging to qualify for a refund.",
    "international_refund": "International orders are not eligible for refunds after 14 days.",
    "shipping_time": "Standard shipping takes 3-5 business days within the country.",
    "warranty": "Products carry a 1-year manufacturer warranty against defects.",
}


@dataclass(frozen=True)
class Query:
    id: str
    text: str
    golden_chunks: tuple[str, ...]  # hand-labeled relevant chunk ids


QUERIES = (
    Query(
        "refund_window",
        "What is the refund window for an unused item bought domestically?",
        ("refund_days", "refund_condition"),
    ),
    Query(
        "shipping",
        "How long does standard shipping take?",
        ("shipping_time",),
    ),
    Query(
        "warranty",
        "What is the warranty period on products?",
        ("warranty",),
    ),
)

def _embedding_model() -> str:
    model = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or os.environ.get(
        "OPENAI_EMBEDDING_MODEL"
    )
    if not model:
        raise ValueError(
            "Set AZURE_OPENAI_EMBEDDING_DEPLOYMENT (or OPENAI_EMBEDDING_MODEL) "
            "in .env to an embeddings deployment, e.g. text-embedding-3-small."
        )
    return model


def embed(client, texts: list[str]) -> list[list[float]]:
    """Real embeddings call. Returns one vector per input text, same order."""
    response = client.embeddings.create(model=_embedding_model(), input=texts)
    return [item.embedding for item in response.data]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def retrieve(query_vector: list[float], chunk_vectors: dict[str, list[float]], k: int) -> list[str]:
    """Real vector-search retriever: rank chunks by cosine similarity to the
    query embedding, same mechanism a production vector database uses.
    Recall/precision misses here come from genuine embedding-space distance,
    not a scripted or keyword-based stand-in.
    """
    scored = [
        (cosine_similarity(query_vector, vec), chunk_id)
        for chunk_id, vec in chunk_vectors.items()
    ]
    scored.sort(key=lambda pair: -pair[0])
    return [chunk_id for _, chunk_id in scored[:k]]


def recall_at_k(query: Query, retrieved: list[str]) -> float:
    found = set(retrieved) & set(query.golden_chunks)
    return len(found) / len(query.golden_chunks)


def precision_at_k(query: Query, retrieved: list[str]) -> float:
    if not retrieved:
        return 0.0
    found = set(retrieved) & set(query.golden_chunks)
    return len(found) / len(retrieved)


# ---------------------------------------------------------------------------
# Generation: real model call, answers only from the retrieved chunks.
# ---------------------------------------------------------------------------

GENERATION_PROMPT = """Answer the user's question using only the provided
context. If the context does not fully answer it, say what is missing.
Keep the answer to 1-2 sentences."""


def generate_answer(client, model: str, query: Query, context_ids: list[str]) -> str:
    context = "\n".join(f"- {CORPUS[cid]}" for cid in context_ids) or "(no context retrieved)"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": GENERATION_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query.text}"},
        ],
        max_completion_tokens=256,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Faithfulness: real LLM judge, claim-by-claim against only the retrieved
# context (reference-free -- no golden answer involved).
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You check whether an answer is faithful to a given context.
Break the answer into individual factual claims. For each claim, decide if
it is directly supported by the context. Reply only JSON with fields:
"total_claims" (integer), "supported_claims" (integer),
"unsupported" (array of the unsupported claim strings)."""


class FaithfulnessJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_claims: int
    supported_claims: int
    unsupported: list[str]


def judge_faithfulness(client, model: str, context_ids: list[str], answer: str) -> FaithfulnessJudgment:
    context = "\n".join(f"- {CORPUS[cid]}" for cid in context_ids) or "(no context retrieved)"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nAnswer:\n{answer}"},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=512,
    )
    return FaithfulnessJudgment.model_validate_json(response.choices[0].message.content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=2, help="top-k chunks to retrieve")
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k must be positive")

    try:
        client, model = make_client()
    except ValueError as exc:
        parser.error(str(exc))

    print(f"LIVE RAG EVAL | {model} | k={args.k}\n")
    rows = []
    with client:
        chunk_ids = list(CORPUS.keys())
        chunk_vectors = dict(zip(chunk_ids, embed(client, [CORPUS[c] for c in chunk_ids])))
        query_vectors = dict(zip((q.id for q in QUERIES), embed(client, [q.text for q in QUERIES])))

        for query in QUERIES:
            retrieved = retrieve(query_vectors[query.id], chunk_vectors, args.k)
            recall = recall_at_k(query, retrieved)
            precision = precision_at_k(query, retrieved)

            print(f"{query.id}")
            print(f"  query: {query.text}")
            print(f"  golden chunks: {list(query.golden_chunks)}")
            print(f"  retrieved (k={args.k}): {retrieved}")
            print(f"  recall@{args.k}={recall:.0%}  precision@{args.k}={precision:.0%}")

            answer = generate_answer(client, model, query, retrieved)
            print(f"  answer: {answer}")

            try:
                judgment = judge_faithfulness(client, model, retrieved, answer)
                faithfulness = (
                    judgment.supported_claims / judgment.total_claims
                    if judgment.total_claims else 1.0
                )
                print(
                    f"  faithfulness: {judgment.supported_claims}/{judgment.total_claims} "
                    f"claims supported ({faithfulness:.0%})"
                )
                if judgment.unsupported:
                    print(f"  unsupported claims: {judgment.unsupported}")
            except ValidationError as exc:
                faithfulness = None
                print(f"  faithfulness: judge response invalid ({exc.__class__.__name__})")

            rows.append((query.id, recall, precision, faithfulness))
            print()

    print("SUMMARY")
    print(f"{'Query':<16}{'Recall@k':<12}{'Precision@k':<14}{'Faithfulness'}")
    for qid, recall, precision, faithfulness in rows:
        faith_str = "n/a" if faithfulness is None else f"{faithfulness:.0%}"
        print(f"{qid:<16}{recall:<12.0%}{precision:<14.0%}{faith_str}")
    print(
        "\nRecall@k and precision@k come from real embeddings-based vector "
        "search (cosine similarity), not a keyword or scripted stand-in. "
        "Faithfulness comes from a live LLM judge grading the real generated "
        "answer against only the retrieved chunks, with no golden answer "
        "involved."
    )


if __name__ == "__main__":
    main()
