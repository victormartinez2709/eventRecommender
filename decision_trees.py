"""
Module 3: Decision Trees tab.

    python decision_trees.py      (after labeled_data.py)

Three decision trees on the numeric format features, with the same
training / testing split as the Naive Bayes tab.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, plot_tree

FIGS = "assets/figures/dectrees/"
DATA = "exports/module3/"
FEATURES = ["start_hour", "weekday", "lineup_size", "lead_time_days", "month"]
LABELS = ["electronic", "not_electronic"]


def table_image(df, title, path, width=9):
    fig, ax = plt.subplots(figsize=(width, 0.3 * len(df) + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.values, colLabels=df.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    ax.set_title(title, fontsize=11, weight="bold")
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def gini(counts):
    p = np.array(counts) / sum(counts)
    return 1 - np.sum(p ** 2)


def entropy(counts):
    p = np.array(counts) / sum(counts)
    p = p[p > 0]
    return -np.sum(p * np.log2(p))


df = pd.read_csv(DATA + "events_labeled.csv")
X = df[FEATURES]
y = df["label"]

#training and testing sets: disjoint, 70% / 30% (same split as Naive Bayes)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
print("train:", X_train.shape, " test:", X_test.shape, " overlap:", len(set(X_train.index) & set(X_test.index)))
X_train.assign(label=y_train).to_csv(DATA + "dt_train.csv")
X_test.assign(label=y_test).to_csv(DATA + "dt_test.csv")

table_image(X.head(8).assign(label=y.head(8)), "Decision tree input: numeric features + label",
            FIGS + "dt_input_sample.png")
table_image(X_train.head(6).assign(label=y_train.head(6)), f"Training set (first 6 of {len(X_train)})",
            FIGS + "train_sample.png")
table_image(X_test.head(6).assign(label=y_test.head(6)), f"Testing set (first 6 of {len(X_test)})",
            FIGS + "test_sample.png")

#three different trees
trees = {
    "Tree 1: Gini, depth 3": DecisionTreeClassifier(criterion="gini", max_depth=3, random_state=42),
    "Tree 2: Entropy, depth 3": DecisionTreeClassifier(criterion="entropy", max_depth=3, random_state=42),
    "Tree 3: Gini, depth 5": DecisionTreeClassifier(criterion="gini", max_depth=5, random_state=42),
}

fig_cm, axes_cm = plt.subplots(1, 3, figsize=(15, 4))
for i, (name, tree) in enumerate(trees.items(), start=1):
    tree.fit(X_train, y_train)
    pred = tree.predict(X_test)
    print(f"\n{name}  accuracy {accuracy_score(y_test, pred):.3f}")
    print(confusion_matrix(y_test, pred, labels=LABELS))

    plt.figure(figsize=(16 if tree.get_depth() < 5 else 30, 7 if tree.get_depth() < 5 else 10))
    plot_tree(tree, feature_names=FEATURES, class_names=list(tree.classes_), filled=True,
              rounded=True, fontsize=9 if tree.get_depth() < 5 else 7, impurity=True)
    plt.title(name, fontsize=14)
    plt.savefig(FIGS + f"tree{i}.png", dpi=130, bbox_inches="tight")
    plt.close()

    ConfusionMatrixDisplay.from_predictions(y_test, pred, labels=LABELS, cmap="Blues",
                                            colorbar=False, ax=axes_cm[i - 1])
    axes_cm[i - 1].set_title(f"{name}\naccuracy {accuracy_score(y_test, pred):.2f}")
fig_cm.tight_layout()
fig_cm.savefig(FIGS + "confusion_matrices.png", dpi=160, bbox_inches="tight")
plt.close(fig_cm)

#train vs test accuracy for each depth
depths = range(1, 13)
train_acc, test_acc = [], []
for d in depths:
    t = DecisionTreeClassifier(max_depth=d, random_state=42).fit(X_train, y_train)
    train_acc.append(t.score(X_train, y_train))
    test_acc.append(t.score(X_test, y_test))
print("\ntrain acc:", np.round(train_acc, 3))
print("test acc: ", np.round(test_acc, 3))

plt.figure(figsize=(7, 3.8))
plt.plot(depths, train_acc, marker="o", label="training set")
plt.plot(depths, test_acc, marker="o", label="testing set")
plt.xlabel("max_depth")
plt.ylabel("accuracy")
plt.title("Deeper trees memorize the training set")
plt.legend()
plt.savefig(FIGS + "depth_vs_accuracy.png", dpi=160, bbox_inches="tight")
plt.close()

#worked example: the root split of Tree 1, by hand
root = trees["Tree 1: Gini, depth 3"].tree_
feat, thr = FEATURES[root.feature[0]], root.threshold[0]
left = X_train[feat] <= thr
counts = lambda s: [int((s == "electronic").sum()), int((s == "not_electronic").sum())]
parent, l, r = counts(y_train), counts(y_train[left]), counts(y_train[~left])
n, nl, nr = sum(parent), sum(l), sum(r)
print(f"\nroot split: {feat} <= {thr:.2f}")
print("counts [electronic, not]: parent", parent, " left", l, " right", r)
print(f"Gini: parent {gini(parent):.3f}  left {gini(l):.3f}  right {gini(r):.3f}  "
      f"weighted {nl / n * gini(l) + nr / n * gini(r):.3f}")
print(f"Entropy: parent {entropy(parent):.3f}  left {entropy(l):.3f}  right {entropy(r):.3f}  "
      f"weighted {nl / n * entropy(l) + nr / n * entropy(r):.3f}")
print(f"Information gain (entropy): {entropy(parent) - nl / n * entropy(l) - nr / n * entropy(r):.3f}")
print(f"Gini decrease: {gini(parent) - nl / n * gini(l) - nr / n * gini(r):.3f}")
