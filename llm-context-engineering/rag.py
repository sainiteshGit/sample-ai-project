"""
rag.py -- RAG done right: chunk -> hybrid (BM25 + vector) -> rerank.

Module 02 - Context Engineering, Lesson 5.

The point of this demo is to show WHY hybrid retrieval beats either method alone:
  - BM25 (lexical) nails exact tokens (IDs, codes, names) but is blind to meaning.
  - Vector (semantic) nails paraphrase/synonyms but fumbles exact tokens.
They fail in OPPOSITE directions, so fusing them wins. Then a reranker does a
precision pass to keep only the top few for the budget.

Everything here is pure Python (numpy is unavailable). The "embedding" is a toy
bag-of-concepts vector, NOT a real model -- the goal is the pipeline behavior,
not embedding quality.

Run:  python3 rag.py
"""

import math
import re

# ---------------- corpus ----------------
DOCS = [
    "To reset your password, go to Settings and click Credential Recovery.",
    "Our refund policy allows returns within 30 days of purchase.",
    "The premium tier costs $20 per month and includes priority support.",
    "Account ACC-7788 is flagged for manual review by the billing team.",
    "Automobiles manufactured before 2005 require an emissions inspection.",
    "To change your login credentials, use the account recovery workflow.",
    "Account ACC-7799 was closed at the customer's request last week.",
    "Priority support responds within one hour for premium subscribers.",
]

# ---------------- tokenization ----------------
def toks(s):
    return re.findall(r"[a-z0-9\-]+", s.lower())

# ---------------- BM25 (lexical) ----------------
def build_bm25(docs):
    corpus = [toks(d) for d in docs]
    N = len(corpus)
    avgdl = sum(len(d) for d in corpus) / N
    df = {}
    for d in corpus:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log(1 + (N - n + 0.5) / (n + 0.5)) for w, n in df.items()}
    return corpus, avgdl, idf

def bm25_score(query, doc_toks, avgdl, idf, k1=1.5, b=0.75):
    score = 0.0
    dl = len(doc_toks)
    for w in toks(query):
        if w not in idf:
            continue
        f = doc_toks.count(w)
        if f == 0:
            continue
        score += idf[w] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
    return score

# ---------------- toy "embedding" (semantic) ----------------
# Map words to a few coarse CONCEPT buckets so paraphrases share a vector.
CONCEPTS = {
    "credentials": {"password", "credential", "credentials", "login", "recovery", "reset"},
    "billing":     {"refund", "returns", "purchase", "billing", "cost", "$20", "premium", "tier"},
    "support":     {"support", "priority", "responds", "hour", "subscribers"},
    "vehicle":     {"automobile", "automobiles", "car", "cars", "emissions", "inspection"},
    "account":     {"account", "acc-7788", "acc-7799", "review", "closed", "flagged"},
}
def embed(s):
    v = {c: 0.0 for c in CONCEPTS}
    for w in toks(s):
        for c, words in CONCEPTS.items():
            if w in words:
                v[c] += 1.0
    return v
def cosine(a, b):
    dot = sum(a[c] * b[c] for c in a)
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    return dot / (na * nb) if na and nb else 0.0

# ---------------- retrieval methods ----------------
def normalize(scores):
    m = max(scores) if scores else 0
    return [s / m if m else 0 for s in scores]

def retrieve(query, corpus, avgdl, idf):
    bm = [bm25_score(query, d, avgdl, idf) for d in corpus]
    qv = embed(query)
    vec = [cosine(qv, embed(DOCS[i])) for i in range(len(DOCS))]
    return normalize(bm), normalize(vec)

def rerank(query, candidates):
    """Toy cross-encoder: score each candidate by joint keyword+concept overlap
    seen TOGETHER with the query. Rewards docs that match BOTH lexically and
    semantically -- the precision pass."""
    qwords = set(toks(query))
    qv = embed(query)
    scored = []
    for i in candidates:
        lex = len(qwords & set(toks(DOCS[i])))
        sem = cosine(qv, embed(DOCS[i]))
        scored.append((lex + 2 * sem, i))
    scored.sort(reverse=True)
    return [i for _, i in scored]

def show(title, ranked, k=3):
    print(f"   {title}:")
    for i in ranked[:k]:
        print(f"      #{i}: {DOCS[i]}")


def run_query(query, corpus, avgdl, idf, want_idx, label):
    print("=" * 74)
    print(f"  QUERY: {query!r}")
    print(f"  ({label}; the ideal answer is doc #{want_idx})")
    print("=" * 74)
    bm, vec = retrieve(query, corpus, avgdl, idf)

    bm_rank = sorted(range(len(DOCS)), key=lambda i: bm[i], reverse=True)
    vec_rank = sorted(range(len(DOCS)), key=lambda i: vec[i], reverse=True)
    fused = [0.5 * bm[i] + 0.5 * vec[i] for i in range(len(DOCS))]
    fused_rank = sorted(range(len(DOCS)), key=lambda i: fused[i], reverse=True)
    reranked = rerank(query, fused_rank[:5])   # wide net (5) -> precise top

    show("BM25-only  (lexical)", bm_rank)
    show("Vector-only (semantic)", vec_rank)
    show("Hybrid (fused)", fused_rank)
    show("Hybrid + rerank", reranked)

    def hit(rank): return "YES" if want_idx in rank[:3] else "NO "
    print()
    print(f"   got doc #{want_idx} in top-3?   "
          f"BM25={hit(bm_rank)}  Vector={hit(vec_rank)}  "
          f"Hybrid={hit(fused_rank)}  Hybrid+rerank={hit(reranked)}")
    print()


if __name__ == "__main__":
    corpus, avgdl, idf = build_bm25(DOCS)

    # Query A: needs MEANING. "how do I change my password" shares NO exact words
    # with doc #5 ("change your login credentials") beyond 'change'/'your'.
    run_query("how do I recover my forgotten password",
              corpus, avgdl, idf, want_idx=0,
              label="paraphrase: 'password/recover' vs 'Credential Recovery'")

    # Query B: needs EXACT TOKEN. The literal ID must not be confused with a
    # semantically-identical neighbor (ACC-7799).
    run_query("what is the status of account ACC-7788",
              corpus, avgdl, idf, want_idx=3,
              label="exact ID: ACC-7788 must not be confused with ACC-7799")

    print("=" * 74)
    print("  TAKEAWAY")
    print("=" * 74)
    print("  - Semantic query: vector shines, BM25 can miss (no shared keywords).")
    print("  - Exact-ID query: BM25 shines, vector can confuse ACC-7788 vs ACC-7799.")
    print("  - Hybrid catches BOTH; rerank puts the single best doc on top.")
    print("  Vector-only is the common beginner mistake. Real RAG is hybrid + rerank.")
