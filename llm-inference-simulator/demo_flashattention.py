"""
Demo: FlashAttention  (module 01, concept 1)
Show that FlashAttention returns the SAME numbers as naive attention, while
moving far less data through "HBM". Pure Python, no numpy.

Run:  python3 demo_flashattention.py

The point is NOT speed here (this is a toy on a CPU) — it is:
  1) the outputs are bit-for-bit identical (online softmax is exact), and
  2) the naive path writes an N*N score matrix to "HBM"; flash never does.
We count "HBM bytes" to make the IO difference visible.
"""
import math
import random

random.seed(0)

# ---- toy sizes (tiny so it prints; scale N up to feel the N^2 blowup) -------
N = 8          # sequence length (tokens)
D = 4          # head_dim
BYTES = 2      # FP16
TILE = 2       # SRAM tile size (rows/cols per block) for flash

# random Q, K, V : N tokens, each a D-dim vector
Q = [[random.uniform(-1, 1) for _ in range(D)] for _ in range(N)]
K = [[random.uniform(-1, 1) for _ in range(D)] for _ in range(N)]
V = [[random.uniform(-1, 1) for _ in range(D)] for _ in range(N)]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


# --------------------------------------------------------------------------- #
# NAIVE attention: build the full N*N score matrix, write it to HBM, read it
# back for softmax, read again for @V.  We COUNT the HBM traffic.
# --------------------------------------------------------------------------- #
def naive_attention():
    hbm_bytes = 0
    scale = 1.0 / math.sqrt(D)

    # scores = Q @ K^T   -> N*N matrix, WRITTEN to HBM
    scores = [[dot(Q[i], K[j]) * scale for j in range(N)] for i in range(N)]
    hbm_bytes += N * N * BYTES          # write scores

    # softmax each row  -> READ scores, WRITE weights
    hbm_bytes += N * N * BYTES          # read scores
    weights = []
    for i in range(N):
        m = max(scores[i])
        exps = [math.exp(s - m) for s in scores[i]]
        s = sum(exps)
        weights.append([e / s for e in exps])
    hbm_bytes += N * N * BYTES          # write weights

    # out = weights @ V  -> READ weights
    hbm_bytes += N * N * BYTES          # read weights
    out = [[sum(weights[i][j] * V[j][d] for j in range(N)) for d in range(D)]
           for i in range(N)]
    return out, hbm_bytes


# --------------------------------------------------------------------------- #
# FLASH attention: tile K/V, keep a RUNNING max + sum + output per query row.
# The N*N matrix is NEVER materialized in HBM; only Q,K,V,out cross the bus.
# --------------------------------------------------------------------------- #
def flash_attention():
    scale = 1.0 / math.sqrt(D)
    # HBM traffic = read Q,K,V once + write out once. No score matrix. O(N*D).
    hbm_bytes = 4 * (N * D * BYTES)

    out = [[0.0] * D for _ in range(N)]
    for i in range(N):                        # each query row (a Q tile of 1)
        m_i = -float("inf")                   # running max
        l_i = 0.0                             # running sum of exp
        acc = [0.0] * D                       # running (unnormalized) output
        for jt in range(0, N, TILE):          # stream K/V in SRAM-sized tiles
            for j in range(jt, min(jt + TILE, N)):
                s = dot(Q[i], K[j]) * scale
                m_new = max(m_i, s)
                # rescale old accumulators to the new max (online softmax)
                corr = math.exp(m_i - m_new) if m_i != -float("inf") else 0.0
                p = math.exp(s - m_new)
                l_i = l_i * corr + p
                for d in range(D):
                    acc[d] = acc[d] * corr + p * V[j][d]
                m_i = m_new
        out[i] = [acc[d] / l_i for d in range(D)]
    return out, hbm_bytes


def max_abs_diff(a, b):
    return max(abs(a[i][d] - b[i][d]) for i in range(len(a)) for d in range(len(a[0])))


naive_out, naive_hbm = naive_attention()
flash_out, flash_hbm = flash_attention()

print("#" * 70)
print(f"# FlashAttention demo   (N={N} tokens, head_dim={D}, tile={TILE})")
print("#" * 70)
print(f"\nmax |naive - flash| over all outputs = {max_abs_diff(naive_out, flash_out):.2e}")
print("  -> identical (online softmax is exact, not an approximation)\n")

print(f"{'path':<16}{'HBM bytes moved':>18}{'scales as':>14}")
print("-" * 48)
print(f"{'naive':<16}{naive_hbm:>18,}{'O(N^2)':>14}")
print(f"{'flash':<16}{flash_hbm:>18,}{'O(N)':>14}")
print(f"\nnaive/flash HBM ratio at N={N}: {naive_hbm/flash_hbm:.1f}x")

print("\nNow watch the ratio explode as the sequence grows (the real point):")
print(f"{'N':>8}{'naive O(N^2) bytes':>22}{'flash O(N) bytes':>20}{'ratio':>10}")
for n in [8, 128, 1024, 4096, 16384]:
    naive_b = 4 * n * n * BYTES          # ~4 passes over the N*N matrix
    flash_b = 4 * n * D * BYTES          # Q,K,V,out only
    print(f"{n:>8}{naive_b:>22,}{flash_b:>20,}{naive_b/flash_b:>9.0f}x")

print("\nTakeaways:")
print("  * flash output == naive output (exact); the win is IO, not math")
print("  * naive writes/reads the N*N score matrix in HBM -> O(N^2) traffic")
print("  * flash streams tiles through SRAM, never materializes it -> O(N)")
print("  * at N=4096 that's ~1000x less attention memory traffic")
