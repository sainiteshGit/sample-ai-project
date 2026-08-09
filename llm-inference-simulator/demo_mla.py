"""
Demo: MLA - Multi-head Latent Attention  (module 01, concept 5)
Show how much KV-cache memory you save by storing ONE small latent per token
and re-expanding it to full per-head K,V on the fly -- and what that does to
how many concurrent users fit on a GPU.  Pure Python, no numpy.

Run:  python3 demo_mla.py

Part A: reconstruct full K,V from a latent (mechanics).
Part B: KV bytes/token and concurrency for MHA vs GQA vs MQA vs MLA.
"""
import random

random.seed(0)

# ---- model / gpu knobs -----------------------------------------------------
LAYERS   = 80
HEADS    = 64
HEAD_DIM = 128
BYTES    = 2                 # FP16
LATENT   = 512              # MLA compressed latent dim (per token, per layer)
GQA_GROUPS = 8              # GQA: 64 query heads share K,V across 8 groups
KV_POOL_GB = 60            # GPU memory left for KV after weights
CTX      = 2000            # tokens of context per request


def kv_bytes_per_token(kind):
    # KV = 2 (K&V) * layers * (#kv vectors) * head_dim * bytes
    if kind == "MHA":
        kv_vectors = HEADS                      # every head its own K,V
        return 2 * LAYERS * kv_vectors * HEAD_DIM * BYTES
    if kind == "GQA":
        kv_vectors = GQA_GROUPS                  # heads share within groups
        return 2 * LAYERS * kv_vectors * HEAD_DIM * BYTES
    if kind == "MQA":
        kv_vectors = 1                           # all heads share one K,V
        return 2 * LAYERS * kv_vectors * HEAD_DIM * BYTES
    if kind == "MLA":
        # store ONE latent per token per layer (not 2*heads*head_dim)
        return LAYERS * LATENT * BYTES


# --- PART A: the mechanic -- reconstruct full K,V from a small latent -------
print("#" * 70)
print("# PART A - MLA reconstructs full per-head K,V from one latent vector")
print("#" * 70)

# a token's compressed latent (what actually lives in the KV cache)
c = [random.uniform(-1, 1) for _ in range(LATENT)]

# learned up-projection matrices (random here) : latent -> full K and V
def make_W(rows, cols):
    return [[random.uniform(-0.05, 0.05) for _ in range(cols)] for _ in range(rows)]

full_dim = HEADS * HEAD_DIM
W_up_K = make_W(full_dim, LATENT)
W_up_V = make_W(full_dim, LATENT)

def matvec(W, x):
    return [sum(W[r][k] * x[k] for k in range(len(x))) for r in range(len(W))]

K_full = matvec(W_up_K, c)         # -> 64*128 = 8192 numbers (all heads' K)
V_full = matvec(W_up_V, c)

print(f"\nstored latent c            : {LATENT} numbers  (this is ALL the cache holds)")
print(f"reconstructed K (all heads): {len(K_full)} numbers  ({HEADS} heads x {HEAD_DIM})")
print(f"reconstructed V (all heads): {len(V_full)} numbers")
print(f"compression at store time  : {full_dim*2} -> {LATENT} numbers "
      f"({full_dim*2/LATENT:.0f}x smaller), re-expanded only at compute time")

# --- PART B: KV size + concurrency across attention variants ---------------
print("\n" + "#" * 70)
print("# PART B - KV cache per token and how many users fit on one GPU")
print(f"# ({LAYERS} layers, {HEADS} heads, head_dim {HEAD_DIM}, FP16, "
      f"{KV_POOL_GB} GB KV pool, {CTX} ctx)")
print("#" * 70)
print(f"\n{'variant':<8}{'KV/token':>12}{'vs MHA':>9}{'token slots':>15}{'~users':>10}{'quality':>12}")
print("-" * 66)
pool_bytes = KV_POOL_GB * 1e9
mha = kv_bytes_per_token("MHA")
quality = {"MHA": "best", "GQA": "good", "MQA": "worse", "MLA": "~MHA"}
for kind in ["MHA", "GQA", "MQA", "MLA"]:
    b = kv_bytes_per_token(kind)
    slots = pool_bytes / b
    users = slots / CTX
    kb = b / 1024
    print(f"{kind:<8}{kb:>10.1f}K{mha/b:>8.1f}x{slots:>15,.0f}{users:>10,.0f}{quality[kind]:>12}")

print("\nTakeaways:")
print("  * MHA stores 64 heads' K,V per token -> biggest cache, fewest users")
print("  * MQA shares ONE K,V -> tiny cache but quality drops")
print("  * MLA stores one LEARNED latent, re-expands on the fly ->")
print("    MQA-like size AT ~MHA quality -> several-x more concurrent users")
print("  * it trades a little extra compute (up-projection) for scarce memory")
print("    -- the right trade because decode is memory-bound (cores idle)")
