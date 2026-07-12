"""
sklearn_version.py — the same task, the way you'd actually ship it.

The from-scratch file exists to SHOW you the training loop. In real life you
don't hand-write backprop — a library does it, correctly and fast. This is the
identical problem in ~15 lines. The training loop is still there; it's just
hidden inside .fit().

Run it:
    python sklearn_version.py
"""

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline

from data import TRAIN_DATA, TEST_DATA

train_texts = [c for c, _ in TRAIN_DATA]
train_labels = [lbl for _, lbl in TRAIN_DATA]

# Text -> numbers (CountVectorizer) piped into a small neural network (MLP).
model = make_pipeline(
    CountVectorizer(),
    MLPClassifier(hidden_layer_sizes=(16,), max_iter=2000, random_state=42),
)

model.fit(train_texts, train_labels)   # <- the whole training loop lives here

print("Inference on held-out comments:\n")
for text, truth in TEST_DATA:
    pred = model.predict([text])[0]
    prob = model.predict_proba([text])[0][1]
    label = "TOXIC" if pred == 1 else "fine"
    mark = "OK " if pred == truth else "XX "
    print(f"  {mark} [{label:5s} {prob:.2f}]  {text}")
