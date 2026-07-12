"""
bias_demo.py — "a model is only as good as its examples."

This is the guide's most important 'honest fine print' made concrete. We train
the SAME network on a SKEWED pile of examples — where the only polite words the
model ever saw were formal, corporate ones — then watch it wrongly flag casual
and dialect-flavored comments it was never shown.

Nothing is wrong with the code. The data is biased, so the model is biased.
That single fact explains most strange AI failures you'll ever hear about.

Run it:
    python bias_demo.py
"""

import numpy as np

from mlp_from_scratch import TinyNeuralNet, build_vocab, vectorize, train, predict

np.random.seed(42)

# A skewed training pile: toxic examples are varied, but the ONLY "fine"
# examples are stiff/formal. The model never sees casual friendliness.
SKEWED_TRAIN = [
    ("you are an idiot", 1),
    ("what a stupid comment", 1),
    ("shut up you moron", 1),
    ("you are pathetic and useless", 1),
    ("what a braindead take", 1),
    ("nobody likes you go away", 1),
    # only formal politeness seen as "fine":
    ("thank you for your detailed correspondence", 0),
    ("i appreciate your thorough analysis", 0),
    ("please find the requested information attached", 0),
    ("kind regards and thank you for your time", 0),
    ("i concur with your well reasoned assessment", 0),
    ("we value your professional contribution", 0),
]

# Casual, friendly comments — obviously fine to a human, but written in a style
# the skewed model never saw.
UNSEEN_CASUAL = [
    "yo this is fire thanks fam",
    "haha nice one that made my day",
    "wicked good stuff mate",
    "lol love it keep em coming",
    "sweet, that totally works for me",
]


def main():
    comments = [c for c, _ in SKEWED_TRAIN]
    labels = np.array([lbl for _, lbl in SKEWED_TRAIN], dtype=np.float32)

    vocab = build_vocab(comments)
    X = np.stack([vectorize(c, vocab) for c in comments])

    net = TinyNeuralNet(n_inputs=len(vocab), n_hidden=16)
    train(net, X, labels, epochs=2000, lr=0.5)

    print("Scoring casual, friendly comments the model was never shown:\n")
    for text in UNSEEN_CASUAL:
        label, score = predict(net, vocab, text)
        flag = "  <-- wrongly flagged!" if label == "TOXIC" else ""
        print(f"  [{label:5s} {score:.2f}]  {text}{flag}")

    print(
        "\nLesson: the code is fine. The DATA was skewed, so the model learned a\n"
        "narrow, biased notion of 'polite'. Fix the data, not the algorithm."
    )


if __name__ == "__main__":
    main()
