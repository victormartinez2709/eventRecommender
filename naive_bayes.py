"""
Module 3: Naive Bayes tab.

    python naive_bayes.py      (after labeled_data.py)

Multinomial NB needs non-negative counts, like word counts in a document.
So each format feature is binned into categories ("start_9pm+", "day_sat",
...) and one-hot encoded: every event becomes a row of 0/1 counts.
Bernoulli NB is run on the same 0/1 data for comparison.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import BernoulliNB, MultinomialNB

FIGS = "assets/figures/naivebayes/"
DATA = "exports/module3/"
DAYS = {0: "sun", 1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat"}


def table_image(df, title, path, width=13, fontsize=8):
    fig, ax = plt.subplots(figsize=(width, 0.3 * len(df) + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.values, colLabels=df.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    ax.set_title(title, fontsize=11, weight="bold")
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


df = pd.read_csv(DATA + "events_labeled.csv")

#we bin each numeric feature into categories (like words)
binned = pd.DataFrame({
    "day": df["weekday"].map(DAYS),
    "start": pd.cut(df["start_hour"], [-1, 18.99, 19.99, 20.99, 24],
                    labels=["before7pm", "7pm", "8pm", "9pm+"]).astype(str),
    "lineup": pd.cut(df["lineup_size"], [-1, 0, 1, 2, 100], labels=["0", "1", "2", "3+"]).astype(str),
    "lead": pd.cut(df["lead_time_days"], [-2, -0.5, 30, 90, 180, 400],
                   labels=["unknown", "under30", "30to90", "90to180", "over180"]).astype(str),
    "season": df["month"].map(lambda m: "fall" if m in (9, 10, 11) else "winter" if m in (12, 1, 2)
                              else "spring" if m in (3, 4, 5) else "summer"),
})

#one-hot encoding: each category becomes a 0/1 count column
X = pd.get_dummies(binned).astype(int)
y = df["label"]

#training and testing sets: disjoint, 70% / 30%, same label balance in both
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
print("train:", X_train.shape, " test:", X_test.shape, " overlap:", len(set(X_train.index) & set(X_test.index)))

X_train.assign(label=y_train).to_csv(DATA + "nb_train.csv")
X_test.assign(label=y_test).to_csv(DATA + "nb_test.csv")

#pictures of the data for the Data Prep section
#the one-hot table is wide, so the picture shows it in two halves
fig, axes = plt.subplots(2, 1, figsize=(14, 4.4))
halves = [list(X.columns[:12]), list(X.columns[12:])]
for ax, cols in zip(axes, halves):
    part = X.head(6)[cols] if cols == halves[0] else X.head(6)[cols].assign(label=y.head(6))
    ax.axis("off")
    tbl = ax.table(cellText=part.values, colLabels=part.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
axes[0].set_title("Naive Bayes input: 0/1 counts (one-hot) + label, first 6 rows", fontsize=11, weight="bold")
fig.savefig(FIGS + "nb_input_sample.png", dpi=170, bbox_inches="tight", facecolor="white")
plt.close(fig)
table_image(binned.loc[X_train.index[:6]].assign(label=y_train[:6]), f"Training set (first 6 of {len(X_train)})",
            FIGS + "train_sample.png", width=9)
table_image(binned.loc[X_test.index[:6]].assign(label=y_test[:6]), f"Testing set (first 6 of {len(X_test)})",
            FIGS + "test_sample.png", width=9)

#multinomial NB (with Laplace smoothing, alpha = 1)
mnb = MultinomialNB(alpha=1)
mnb.fit(X_train, y_train)
pred_mnb = mnb.predict(X_test)

#Bernoulli NB on the same data
bnb = BernoulliNB(alpha=1)
bnb.fit(X_train, y_train)
pred_bnb = bnb.predict(X_test)

for name, pred in [("Multinomial NB", pred_mnb), ("Bernoulli NB", pred_bnb)]:
    print(f"\n{name} accuracy: {accuracy_score(y_test, pred):.3f}")
    print(confusion_matrix(y_test, pred, labels=["electronic", "not_electronic"]))

#confusion matrices
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, (name, pred) in zip(axes, [("Multinomial NB", pred_mnb), ("Bernoulli NB", pred_bnb)]):
    ConfusionMatrixDisplay.from_predictions(y_test, pred, labels=["electronic", "not_electronic"],
                                            cmap="Blues", colorbar=False, ax=ax)
    ax.set_title(f"{name}: accuracy {accuracy_score(y_test, pred):.2f}")
fig.tight_layout()
fig.savefig(FIGS + "confusion_matrices.png", dpi=160, bbox_inches="tight")
plt.close(fig)

#which categories point to "electronic": P(category | electronic) / P(category | not electronic)
probs = pd.DataFrame(np.exp(mnb.feature_log_prob_).T, index=X.columns, columns=mnb.classes_)
ratio = (probs["electronic"] / probs["not_electronic"]).sort_values()
print("\n", ratio.round(2))

plt.figure(figsize=(7, 6.5))
plt.barh(ratio.index, ratio.values, color=["#2a78d6" if r > 1 else "#bbbbbb" for r in ratio.values])
plt.axvline(1, color="k", linewidth=1)
plt.xscale("log")
plt.xlabel("P(category | electronic) / P(category | not electronic)")
plt.title("Which categories point to an electronic event")
plt.savefig(FIGS + "category_ratios.png", dpi=160, bbox_inches="tight")
plt.close()
