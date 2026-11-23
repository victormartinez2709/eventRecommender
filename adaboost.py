"""
Module 4: AdaBoost tab.

    python adaboost.py      (after labeled_data.py and decision_trees.py from Module 3)

Same labeled events and the same training / testing split as the Naive Bayes
and Decision Trees tabs. AdaBoost needs numbers: the weekday is a category
(Friday is not "5 times Monday"), so it is one-hot encoded into 7 columns.
The number of rounds and the learning rate are chosen with 5-fold cross
validation on the training set only; the testing set is used once, at the end.
"""

import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import AdaBoostClassifier
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.tree import DecisionTreeClassifier

FIGS = "assets/figures/adaboost/"
DATA3 = "exports/module3/"
DATA4 = "exports/module4/"
BLUE, ORANGE = "#2a78d6", "#eb6834"
LABELS = ["electronic", "not_electronic"]
DAYS = {0: "sun", 1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat"}
RATES = [0.05, 0.1, 0.25, 0.5, 1.0]
MAX_ROUNDS = 400
#staged_score gives a harmless feature-name warning on every round
warnings.filterwarnings("ignore", message="X does not have valid feature names")


def table_image(df, title, path, width=13, fontsize=8):
    fig, ax = plt.subplots(figsize=(width, 0.3 * len(df) + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.astype(object).values, colLabels=df.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    ax.set_title(title, fontsize=11, weight="bold")
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def stump():
    return DecisionTreeClassifier(max_depth=1, random_state=42)


df = pd.read_csv(DATA3 + "events_labeled.csv")
y = df["label"]

#one-hot encoding: the weekday becomes 7 columns of 0/1
day = df["weekday"].map(DAYS)
onehot = pd.get_dummies(day, prefix="day").astype(int)[["day_" + d for d in DAYS.values()]]
X = pd.concat([df[["start_hour", "lineup_size", "lead_time_days", "month"]], onehot], axis=1)
print("X:", X.shape)

before = df.head(6)[["start_hour", "weekday", "lineup_size", "lead_time_days", "month"]].copy()
before.insert(2, "day", day.head(6))
table_image(before, "Before: weekday is a category", FIGS + "onehot_before.png", width=7)
table_image(X.head(6), "After: the weekday is 7 columns of 0/1", FIGS + "onehot_after.png", width=13)

#training and testing sets: disjoint, 70% / 30% (same split as Naive Bayes and Decision Trees)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
print("train:", X_train.shape, " test:", X_test.shape, " overlap:", len(set(X_train.index) & set(X_test.index)))
X_train.assign(label=y_train).to_csv(DATA4 + "ada_train.csv")
X_test.assign(label=y_test).to_csv(DATA4 + "ada_test.csv")
table_image(X_train.assign(label=y_train).head(6).reset_index(), f"Training set (first 6 of {len(X_train)})",
            FIGS + "train_sample.png", width=16, fontsize=7.5)
table_image(X_test.assign(label=y_test).head(6).reset_index(), f"Testing set (first 6 of {len(X_test)})",
            FIGS + "test_sample.png", width=16, fontsize=7.5)

#baseline: one stump
one = stump().fit(X_train, y_train)
print(f"\nsingle stump: splits on {X.columns[one.tree_.feature[0]]} <= {one.tree_.threshold[0]:.2f}, "
      f"test accuracy {one.score(X_test, y_test):.3f}")

#round 1 by hand (labels as +1 / -1)
ypm = np.where(y_train == "electronic", 1, -1)
w = np.full(len(y_train), 1 / len(y_train))
h1 = stump().fit(X_train, y_train, sample_weight=w)
miss = np.where(h1.predict(X_train) == "electronic", 1, -1) != ypm
eps1 = w[miss].sum()
alpha1 = 0.5 * np.log((1 - eps1) / eps1)
w2 = w * np.exp(np.where(miss, alpha1, -alpha1))
w2 = w2 / w2.sum()
print(f"\nround 1 by hand: missed {miss.sum()} of {len(w)}, error {eps1:.4f}, alpha {alpha1:.4f}")
print(f"  weight of each missed event {w[0]:.5f} -> {w2[miss][0]:.5f}, each correct one -> {w2[~miss][0]:.5f}")
print(f"  share of the total weight on the missed events after the update: {w2[miss].sum():.3f}")

#choosing the learning rate and the number of rounds: 5-fold CV on the training set
folds = StratifiedKFold(5, shuffle=True, random_state=42)
curves = {}
for lr in RATES:
    scores = []
    for tr, va in folds.split(X_train, y_train):
        m = AdaBoostClassifier(estimator=stump(), n_estimators=MAX_ROUNDS, learning_rate=lr,
                               random_state=42).fit(X_train.iloc[tr], y_train.iloc[tr])
        scores.append(list(m.staged_score(X_train.iloc[va], y_train.iloc[va])))
    curves[lr] = np.mean(scores, axis=0)
    print(f"learning rate {lr:<5} best CV accuracy {curves[lr].max():.3f} at {curves[lr].argmax() + 1} rounds, "
          f"after {MAX_ROUNDS} rounds {curves[lr][-1]:.3f}")
best_lr = max(RATES, key=lambda r: curves[r].max())
best_n = int(curves[best_lr].argmax() + 1)
print(f"chosen: learning rate {best_lr}, {best_n} rounds")
pd.DataFrame(curves, index=np.arange(1, MAX_ROUNDS + 1)).to_csv(DATA4 + "ada_cv_curves.csv", index_label="rounds")

#CV accuracy as rounds are added
plt.figure(figsize=(8, 4.3))
for lr, col in zip(RATES, ["#b9b9b9", "#8c8c8c", "#5ba3e6", BLUE, ORANGE]):
    plt.plot(np.arange(1, MAX_ROUNDS + 1), curves[lr], lw=1.4, color=col, label=f"learning rate {lr}")
plt.scatter([best_n], [curves[best_lr][best_n - 1]], color="k", zorder=5, s=30)
plt.annotate(f"chosen: {best_n} rounds, rate {best_lr}", (best_n, curves[best_lr][best_n - 1]),
             xytext=(-150, -4), textcoords="offset points", fontsize=8)
plt.xscale("log")
plt.xlabel("number of rounds (stumps), log scale")
plt.ylabel("validation accuracy (5-fold CV)")
plt.title("Validation accuracy as rounds are added")
plt.legend(fontsize=8)
plt.savefig(FIGS + "cv_accuracy_by_rounds.png", dpi=160, bbox_inches="tight")
plt.close()

#the chosen model, trained on the whole training set and tested once
ada = AdaBoostClassifier(estimator=stump(), n_estimators=best_n, learning_rate=best_lr, random_state=42)
ada.fit(X_train, y_train)
pred = ada.predict(X_test)
acc = accuracy_score(y_test, pred)
el = list(ada.classes_).index("electronic")
auc = roc_auc_score(y_test == "electronic", ada.predict_proba(X_test)[:, el])
print(f"\nAdaBoost ({best_n} stumps, rate {best_lr}): train accuracy {ada.score(X_train, y_train):.3f}, "
      f"test accuracy {acc:.3f}, ROC AUC {auc:.3f}")
print(confusion_matrix(y_test, pred, labels=LABELS))

#what the first stumps ask, and their say (sklearn's weight is 2 x the lecture's alpha)
rows = []
for i, (est, wgt, err) in enumerate(zip(ada.estimators_[:8], ada.estimator_weights_, ada.estimator_errors_), 1):
    f, t = est.tree_.feature[0], est.tree_.threshold[0]
    left = est.classes_[est.tree_.value[1][0].argmax()]
    right = est.classes_[est.tree_.value[2][0].argmax()]
    rows.append({"round": i, "question": f"{X.columns[f]} <= {t:.2f}", "if yes": left, "if no": right,
                 "weighted error": round(err, 3), "alpha (lecture)": round(wgt / 2, 3)})
first = pd.DataFrame(rows)
print(first.to_string(index=False))
table_image(first, "The first 8 stumps of the chosen model", FIGS + "first_stumps.png", width=14)

#which features the stumps use, weighted by their say
imp = pd.Series(ada.feature_importances_, index=X.columns).sort_values()
plt.figure(figsize=(6.5, 4))
plt.barh(imp.index, imp.values, color=BLUE)
plt.xlabel("share of the total importance")
plt.title("Which features the stumps rely on")
plt.savefig(FIGS + "feature_importance.png", dpi=160, bbox_inches="tight")
plt.close()

#comparison with the Module 3 decision trees (same split)
trees = {"Tree 1: Gini, depth 3": DecisionTreeClassifier(criterion="gini", max_depth=3, random_state=42),
         "Tree 2: Entropy, depth 3": DecisionTreeClassifier(criterion="entropy", max_depth=3, random_state=42),
         "Tree 3: Gini, depth 5": DecisionTreeClassifier(criterion="gini", max_depth=5, random_state=42)}
F5 = ["start_hour", "weekday", "lineup_size", "lead_time_days", "month"]
results = [{"model": "Single stump", "accuracy": one.score(X_test, y_test)}]
for name, t in trees.items():
    t.fit(df.loc[X_train.index, F5], y_train)
    results.append({"model": name, "accuracy": t.score(df.loc[X_test.index, F5], y_test)})
results.append({"model": f"AdaBoost ({best_n} stumps)", "accuracy": acc})
results = pd.DataFrame(results)
results["correct of 144"] = (results["accuracy"] * len(y_test)).round().astype(int)
print("\n" + results.round(3).to_string(index=False))
results.to_csv(DATA4 + "ada_vs_trees.csv", index=False)

#confusion matrices: best Module 3 tree and AdaBoost
t3 = trees["Tree 3: Gini, depth 5"]
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
ConfusionMatrixDisplay.from_predictions(y_test, t3.predict(df.loc[X_test.index, F5]), labels=LABELS,
                                        cmap="Blues", colorbar=False, ax=axes[0])
axes[0].set_title(f"Best decision tree (Tree 3)\naccuracy {t3.score(df.loc[X_test.index, F5], y_test):.2f}")
ConfusionMatrixDisplay.from_predictions(y_test, pred, labels=LABELS, cmap="Blues", colorbar=False, ax=axes[1])
axes[1].set_title(f"AdaBoost, {best_n} stumps, rate {best_lr}\naccuracy {acc:.2f}")
fig.tight_layout()
fig.savefig(FIGS + "confusion_matrices.png", dpi=160, bbox_inches="tight")
plt.close(fig)
