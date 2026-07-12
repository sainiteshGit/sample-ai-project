"""
mlp_from_scratch.py — the whole guide, in runnable code, using only NumPy.

Run it:
    python mlp_from_scratch.py

You will watch the four-step training loop from the guide play out for real:
    1. show an example        -> forward pass  (the model guesses)
    2. tell it the answer      -> loss          (its "score of wrongness")
    3. nudge the knobs         -> backprop      (backwards blame-assignment)
    4. repeat millions of times-> the epoch loop

Nothing here is magic. It is multiply, add, nudge — exactly what the guide says.
No ML library does the learning for you; every line is visible.
"""

import numpy as np

from data import TRAIN_DATA, TEST_DATA

np.random.seed(42)  # so your run matches the blog's numbers


# ---------------------------------------------------------------------------
# STEP A: turn text into numbers ("how does a comment become numbers?")
# ---------------------------------------------------------------------------
# The simplest possible scheme: a "bag of words". We build a vocabulary from the
# training comments, then represent each comment as a vector counting how often
# each vocabulary word appears. A computer only handles numbers; this is how we
# get there. (Real systems use smarter schemes — a later post covers those.)

def build_vocab(comments):
    vocab = {}
    for text in comments:
        for word in text.split():
            if word not in vocab:
                vocab[word] = len(vocab)
    return vocab


def vectorize(text, vocab):
    vec = np.zeros(len(vocab), dtype=np.float32)
    for word in text.split():
        if word in vocab:
            vec[vocab[word]] += 1.0
    return vec


# ---------------------------------------------------------------------------
# STEP B: the factory of dials (a tiny neural network)
# ---------------------------------------------------------------------------
# One hidden layer + one output. Every weight is a "knob" from the guide. They
# start RANDOM, which is why the first guesses are garbage.

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


class TinyNeuralNet:
    def __init__(self, n_inputs, n_hidden=16):
        # These four arrays ARE the "billion knobs" — just far fewer of them.
        self.W1 = np.random.randn(n_inputs, n_hidden) * 0.1
        self.b1 = np.zeros(n_hidden)
        self.W2 = np.random.randn(n_hidden, 1) * 0.1
        self.b2 = np.zeros(1)

    def forward(self, X):
        # "multiply, add, pass forward" — twice, with a bend in between.
        self.X = X
        self.z1 = X @ self.W1 + self.b1
        self.a1 = np.maximum(0, self.z1)          # ReLU: the "bend" that lets
        self.z2 = self.a1 @ self.W2 + self.b2     # the factory learn curves,
        self.out = sigmoid(self.z2)               # not just straight lines.
        return self.out

    def backward(self, y_true, lr):
        # Backpropagation: work BACKWARDS through the factory and compute, for
        # every knob, "would nudging you up or down have made us less wrong?"
        m = y_true.shape[0]
        y = y_true.reshape(-1, 1)

        dz2 = (self.out - y) / m                   # error at the output
        dW2 = self.a1.T @ dz2
        db2 = dz2.sum(axis=0)

        da1 = dz2 @ self.W2.T
        dz1 = da1 * (self.z1 > 0)                  # gradient through the ReLU
        dW1 = self.X.T @ dz1
        db1 = dz1.sum(axis=0)

        # The nudge: every knob steps a tiny amount toward "less wrong".
        self.W2 -= lr * dW2
        self.b2 -= lr * db2
        self.W1 -= lr * dW1
        self.b1 -= lr * db1


def bce_loss(pred, y):
    # "Score of wrongness": how far each guess was from the true label.
    eps = 1e-8
    y = y.reshape(-1, 1)
    return -np.mean(y * np.log(pred + eps) + (1 - y) * np.log(1 - pred + eps))


# ---------------------------------------------------------------------------
# STEP C: the training loop (the "hotter / colder" game, played fast)
# ---------------------------------------------------------------------------

def train(net, X, y, epochs=2000, lr=0.5):
    print("\nTraining — watch the 'wrongness' fall:\n")
    for epoch in range(epochs):
        pred = net.forward(X)          # 1 + 2: guess
        loss = bce_loss(pred, y)       # 3: measure wrongness
        net.backward(y, lr)            # 4: nudge the knobs
        if epoch % 200 == 0 or epoch == epochs - 1:
            acc = ((pred > 0.5).astype(int).ravel() == y).mean()
            print(f"  epoch {epoch:5d}   wrongness={loss:.4f}   accuracy={acc:.0%}")
    print()


# ---------------------------------------------------------------------------
# STEP D: inference (use the FROZEN model to score new comments)
# ---------------------------------------------------------------------------

def predict(net, vocab, text):
    x = vectorize(text, vocab).reshape(1, -1)
    score = float(net.forward(x)[0, 0])   # knobs frozen — this is not learning
    label = "TOXIC" if score > 0.5 else "fine"
    return label, score


def main():
    comments = [c for c, _ in TRAIN_DATA]
    labels = np.array([lbl for _, lbl in TRAIN_DATA], dtype=np.float32)

    # Text -> numbers
    vocab = build_vocab(comments)
    X = np.stack([vectorize(c, vocab) for c in comments])
    print(f"Training data : {len(comments)} labeled comments")
    print(f"Vocabulary    : {len(vocab)} unique words")
    print(f"Weights (knobs): {len(vocab) * 16 + 16 * 1 + 16 + 1} parameters")

    # Build the factory and train it
    net = TinyNeuralNet(n_inputs=len(vocab), n_hidden=16)
    train(net, X, labels, epochs=2000, lr=0.5)

    # Check it generalizes to comments it never saw (held-out test set)
    print("Inference on comments the model NEVER saw during training:\n")
    correct = 0
    for text, truth in TEST_DATA:
        label, score = predict(net, vocab, text)
        ok = int(label == "TOXIC") == truth
        correct += ok
        mark = "OK " if ok else "XX "
        print(f"  {mark} [{label:5s} {score:.2f}]  {text}")
    print(f"\nHeld-out accuracy: {correct}/{len(TEST_DATA)}\n")

    # Try your own comment
    print("Type a comment to score it (blank line to quit):")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        label, score = predict(net, vocab, text)
        print(f"   -> {label}  (score {score:.2f})")


if __name__ == "__main__":
    main()
