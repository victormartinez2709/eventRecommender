"""
Module 4: Regression tab, part 2 (logistic regression).

    python logistic_regression.py      (after naive_bayes.py from Module 3)

Same question as the Naive Bayes tab: is an event electronic, from its format
alone? It uses the same labeled events, the same 0/1 category columns and the
same training / testing split as Naive Bayes, so the two models can be
compared directly. One category per group is dropped as the baseline
(Sunday, before 7 pm, 1 artist, on sale 90-180 days ahead, fall), so every
coefficient means "compared with the baseline".
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (ConfusionMatrixDisplay, RocCurveDisplay, accuracy_score,
                             confusion_matrix, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.naive_bayes import MultinomialNB

FIGS = "assets/figures/regression/"
DATA3 = "exports/module3/"
DATA4 = "exports/module4/"
BLUE, ORANGE = "#2a78d6", "#eb6834"
LABELS = ["electronic", "not_electronic"]
BASELINE = ["day_sun", "start_before7pm", "lineup_1", "lead_90to180", "season_fall"]


def table_image(df, title, path, width=13, fontsize=8):
    fig, ax = plt.subplots(figsize=(width, 0.3 * len(df) + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.astype(object).values, colLabels=df.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    ax.set_title(title, fontsize=11, weight="bold")
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


#the Naive Bayes training and testing sets (Module 3): 24 columns of 0/1 + label
train = pd.read_csv(DATA3 + "nb_train.csv", index_col=0)
test = pd.read_csv(DATA3 + "nb_test.csv", index_col=0)
print("train:", train.shape, " test:", test.shape, " overlap:", len(set(train.index) & set(test.index)))

#the target must be two classes: 1 = electronic, 0 = not electronic
y_train = (train["label"] == "electronic").astype(int)
y_test = (test["label"] == "electronic").astype(int)
#one baseline column per group is dropped
X_train = train.drop(columns=["label"] + BASELINE)
X_test = test.drop(columns=["label"] + BASELINE)

X_train.assign(electronic=y_train).to_csv(DATA4 + "logit_train.csv")
X_test.assign(electronic=y_test).to_csv(DATA4 + "logit_test.csv")
short = {c: c.replace("start_", "").replace("lineup_", "art_").replace("season_", "")
            .replace("lead_", "").replace("to", "-").replace("unknown", "unkn").replace("day_", "")
         for c in X_train.columns}
table_image(X_train.rename(columns=short).assign(electronic=y_train).head(6).reset_index(),
            f"Training set (first 6 of {len(X_train)})", FIGS + "logit_train_sample.png", width=15, fontsize=7)
table_image(X_test.rename(columns=short).assign(electronic=y_test).head(6).reset_index(),
            f"Testing set (first 6 of {len(X_test)})", FIGS + "logit_test_sample.png", width=15, fontsize=7)

#checking the encoding with 5-fold cross validation on the training set only
labeled = pd.read_csv(DATA3 + "events_labeled.csv")
raw = labeled.loc[X_train.index, ["start_hour", "weekday", "lineup_size", "lead_time_days", "month"]]
folds = StratifiedKFold(5, shuffle=True, random_state=42)
cv_raw = cross_val_score(LogisticRegression(max_iter=5000), raw, y_train, cv=folds).mean()
cv_cat = cross_val_score(LogisticRegression(max_iter=5000), X_train, y_train, cv=folds).mean()
print(f"\n5-fold CV accuracy on the training set: raw numbers {cv_raw:.3f}, 0/1 categories {cv_cat:.3f}")

#the model
logit = LogisticRegression(max_iter=5000)
logit.fit(X_train, y_train)
pred = logit.predict(X_test)
prob = logit.predict_proba(X_test)[:, 1]
acc = accuracy_score(y_test, pred)
print(f"\nlogistic regression: test accuracy {acc:.3f}   ROC AUC {roc_auc_score(y_test, prob):.3f}")
print(confusion_matrix(y_test, pred, labels=[1, 0]))

coef = pd.Series(logit.coef_[0], index=X_train.columns)
print(f"\nintercept b0 = {logit.intercept_[0]:.3f}")
print(pd.DataFrame({"b": coef, "odds x": np.exp(coef)}).round(2).sort_values("b").to_string())
pd.DataFrame({"coefficient": coef, "odds_ratio": np.exp(coef)}).to_csv(DATA4 + "logit_coefficients.csv")

#worked example: Saturday, 9 pm or later, 1 artist, on sale under 30 days ahead, fall
ex = pd.DataFrame(0, index=[0], columns=X_train.columns)
ex[["day_sat", "start_9pm+", "lead_under30"]] = 1
z = logit.intercept_[0] + (ex.iloc[0] * coef).sum()
print(f"\nexample event: z = {z:.3f},  p = 1/(1+e^-z) = {1 / (1 + np.exp(-z)):.3f}")
print("terms:", {c: round(coef[c], 3) for c in ["day_sat", "start_9pm+", "lead_under30"]})

#Naive Bayes from Module 3 on the same columns, for the comparison
nb = MultinomialNB(alpha=1).fit(train.drop(columns="label"), train["label"])
nb_pred = nb.predict(test.drop(columns="label"))
nb_prob = nb.predict_proba(test.drop(columns="label"))[:, list(nb.classes_).index("electronic")]
nb_acc = accuracy_score(test["label"], nb_pred)
print(f"\nNaive Bayes: test accuracy {nb_acc:.3f}   ROC AUC {roc_auc_score(y_test, nb_prob):.3f}")
same = (np.where(pred == 1, "electronic", "not_electronic") == nb_pred).sum()
print(f"the two models agree on {same} of {len(test)} test events")

#confusion matrices side by side
lab = np.where(pred == 1, "electronic", "not_electronic")
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
ConfusionMatrixDisplay.from_predictions(test["label"], lab, labels=LABELS, cmap="Blues",
                                        colorbar=False, ax=axes[0])
axes[0].set_title(f"Logistic regression\naccuracy {acc:.2f}")
ConfusionMatrixDisplay.from_predictions(test["label"], nb_pred, labels=LABELS, cmap="Blues",
                                        colorbar=False, ax=axes[1])
axes[1].set_title(f"Naive Bayes (Module 3)\naccuracy {nb_acc:.2f}")
fig.tight_layout()
fig.savefig(FIGS + "logit_confusion.png", dpi=160, bbox_inches="tight")
plt.close(fig)

#ROC curves
fig, ax = plt.subplots(figsize=(5.2, 5))
RocCurveDisplay.from_predictions(y_test, prob, name="Logistic regression", ax=ax, color=BLUE)
RocCurveDisplay.from_predictions(y_test, nb_prob, name="Naive Bayes", ax=ax, color=ORANGE)
ax.plot([0, 1], [0, 1], "k--", lw=1)
ax.set_title("ROC curves on the 144 test events")
fig.savefig(FIGS + "logit_roc.png", dpi=160, bbox_inches="tight")
plt.close(fig)

#odds ratios
odds = np.exp(coef).sort_values()
plt.figure(figsize=(7, 5.5))
plt.barh(odds.index, odds.values, color=[BLUE if v > 1 else ORANGE for v in odds.values])
plt.axvline(1, color="k", lw=0.8)
plt.xscale("log")
ticks = [0.5, 1, 2, 4, 6]
plt.xticks(ticks, [str(t) for t in ticks])
plt.minorticks_off()
plt.xlabel("odds ratio e^b (log scale): above 1 = more likely electronic")
plt.title("What each category does to the odds of an electronic event\n"
          "(compared with Sunday, before 7 pm, 1 artist, on sale 90-180 days ahead, fall)", fontsize=10)
plt.savefig(FIGS + "logit_odds_ratios.png", dpi=160, bbox_inches="tight")
plt.close()

#every test event on the sigmoid
z_test = logit.decision_function(X_test)
zz = np.linspace(-6, 6, 200)
plt.figure(figsize=(7, 4))
plt.plot(zz, 1 / (1 + np.exp(-zz)), color="grey", lw=1.5)
jitter = np.random.default_rng(42).normal(0, 0.015, len(z_test))
plt.scatter(z_test[y_test == 1], prob[y_test == 1] + jitter[y_test == 1], s=16, color=ORANGE,
            alpha=0.8, label="truly electronic")
plt.scatter(z_test[y_test == 0], prob[y_test == 0] + jitter[y_test == 0], s=16, color=BLUE,
            alpha=0.6, label="truly not electronic")
plt.axhline(0.5, color="k", ls="--", lw=1)
plt.text(-5.8, 0.53, "p = 0.5: above it the model says electronic", fontsize=8)
plt.xlabel("linear score z = b0 + b1x1 + ... ")
plt.ylabel("P(electronic)")
plt.title("The 144 test events on the sigmoid")
plt.legend(fontsize=8, loc="lower right")
plt.savefig(FIGS + "logit_sigmoid_test.png", dpi=160, bbox_inches="tight")
plt.close()

pd.DataFrame([{"model": "Naive Bayes (multinomial)", "accuracy": nb_acc, "roc_auc": roc_auc_score(y_test, nb_prob)},
              {"model": "Logistic regression", "accuracy": acc, "roc_auc": roc_auc_score(y_test, prob)}]
             ).to_csv(DATA4 + "logit_vs_nb.csv", index=False)
