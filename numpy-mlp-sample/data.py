"""
data.py — the labeled examples ("training data" in the guide).

Every row is (comment, label) where label is 1 = toxic, 0 = fine.
Notice a few things that map straight back to the guide:

  * "id1ot" and "you're a clown" — disguised / polite-sounding toxicity that a
    keyword blocklist would miss, but examples teach the model to catch.
  * "wicked good", "bloody brilliant" — friendly phrases a naive blocklist
    would wrongly flag. The labels teach the model these are FINE.

This is deliberately tiny (readable in one screen) so you can see the whole
pipeline. Real datasets have 100,000+ rows — the code below does not change.
"""

TRAIN_DATA = [
    # --- toxic (label 1) ---
    ("you are an idiot and everyone knows it", 1),
    ("what a stupid worthless comment", 1),
    ("shut up you moron nobody wants you here", 1),
    ("you're an absolute clown honestly", 1),
    ("get lost you id1ot", 1),
    ("this is the dumbest thing i have ever read", 1),
    ("you people are pathetic losers", 1),
    ("i hope you fail miserably you fool", 1),
    ("what a garbage take from a garbage person", 1),
    ("nobody likes you go away trash", 1),
    ("you are so dumb it is embarrassing", 1),
    ("only an imbecile would write this", 1),
    ("you're useless and always have been", 1),
    ("kill this thread it is as stupid as you", 1),
    ("what a braindead opinion", 1),

    # --- fine (label 0) ---
    ("this recipe is wicked good thanks for sharing", 0),
    ("bloody brilliant work on the new release", 0),
    ("i disagree but i see your point", 0),
    ("thanks for the detailed explanation", 0),
    ("could you clarify the second step please", 0),
    ("great job on the presentation today", 0),
    ("i learned a lot from this article", 0),
    ("that is a fair criticism let me revise it", 0),
    ("looking forward to the next update", 0),
    ("nice catch i will fix that bug", 0),
    ("the weather is lovely this morning", 0),
    ("appreciate you taking the time to reply", 0),
    ("this helped me understand the concept", 0),
    ("welcome to the community glad you are here", 0),
    ("solid analysis with good sources", 0),
]

# Held-out comments the model never saw during training — used to check it
# actually learned the pattern instead of memorizing the training rows.
TEST_DATA = [
    ("you are a complete fool", 1),
    ("what a worthless idea", 1),
    ("shut up nobody asked", 1),
    ("thanks this is really helpful", 0),
    ("great point i had not considered that", 0),
    ("could we schedule a call to discuss", 0),
]
