"""
Module 4: Regression tab, part 1 (linear regression).

    python linear_regression.py      (after lead_time_data.py)

Predicts how many days before the event tickets go on sale (lead_time_days)
from the format of the event, the headliner and the venue.
The venue is a category, so it is one-hot encoded ("other" is the baseline).
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

FIGS = "assets/figures/regression/"
DATA = "exports/module4/"
BLUE, ORANGE = "#2a78d6", "#eb6834"
NUMERIC = ["is_electronic", "start_hour", "fri_sat", "lineup_size",
           "headliner_shows_log2", "days_out"]


def table_image(df, title, path, width=13, fontsize=8):
    fig, ax = plt.subplots(figsize=(width, 0.3 * len(df) + 1))
    ax.axis("off")
    tbl = ax.table(cellText=df.astype(object).values, colLabels=df.columns, cellLoc="left", bbox=[0, 0, 1, 1])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    ax.set_title(title, fontsize=11, weight="bold")
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def short(name, n=22):
    return name if len(name) <= n else name[:n - 1] + "."


df = pd.read_csv(DATA + "lead_time_events.csv")

#one-hot encoding of the venue: one 0/1 column per venue, "other" is the baseline (all zeros)
venues = pd.get_dummies(df["venue_group"], prefix="venue").astype(int).drop(columns="venue_other")
X = pd.concat([df[NUMERIC], venues], axis=1)
y = df["lead_time_days"]
print("X:", X.shape, " venue columns:", venues.shape[1])

show = df.head(8)[["name", "venue", "local_date"] + NUMERIC + ["lead_time_days"]].copy()
show["name"] = show["name"].str.slice(0, 20)
show["venue"] = show["venue"].fillna("").str.slice(0, 17)
table_image(show, "Linear regression data: one row per event, target = lead_time_days",
            FIGS + "lr_data_sample.png", width=17, fontsize=7.5)

onehot = df.head(6)[["venue_group"]].copy()
onehot["venue_group"] = onehot["venue_group"].map(short)
v6 = venues.head(6)
v6 = v6.loc[:, (v6.sum() > 0)]
v6.columns = [short(c.replace("venue_", ""), 16) for c in v6.columns]
table_image(pd.concat([onehot, v6], axis=1),
            "One-hot encoding of the venue (only the columns used by these 6 rows are shown)",
            FIGS + "lr_onehot_venue.png", width=13)

#training and testing sets: disjoint, 70% / 30%, same share of electronic events in both
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42,
                                                    stratify=df["is_electronic"])
print("train:", X_train.shape, " test:", X_test.shape, " overlap:", len(set(X_train.index) & set(X_test.index)))
X_train.assign(lead_time_days=y_train).to_csv(DATA + "lr_train.csv")
X_test.assign(lead_time_days=y_test).to_csv(DATA + "lr_test.csv")
cols6 = NUMERIC + ["lead_time_days"]
table_image(X_train.assign(lead_time_days=y_train)[cols6].head(6).reset_index(),
            f"Training set (first 6 of {len(X_train)}, venue columns not shown)", FIGS + "lr_train_sample.png")
table_image(X_test.assign(lead_time_days=y_test)[cols6].head(6).reset_index(),
            f"Testing set (first 6 of {len(X_test)}, venue columns not shown)", FIGS + "lr_test_sample.png")

#the model
lr = LinearRegression()
lr.fit(X_train, y_train)
pred_train = lr.predict(X_train)
pred = lr.predict(X_test)

rmse = np.sqrt(mean_squared_error(y_test, pred))
mae = mean_absolute_error(y_test, pred)
r2 = r2_score(y_test, pred)
base = np.sqrt(mean_squared_error(y_test, np.full(len(y_test), y_train.mean())))
print(f"\ntest RMSE {rmse:.1f} days   MAE {mae:.1f} days   R2 {r2:.3f}")
print(f"train R2 {r2_score(y_train, pred_train):.3f}   baseline RMSE (always the training mean) {base:.1f} days")

coef = pd.Series(lr.coef_, index=X.columns)
print(f"\nintercept {lr.intercept_:.1f}")
print(coef.round(2).to_string())
coef.rename("coefficient_days").to_csv(DATA + "lr_coefficients.csv")

#for comparison: electronic alone (just the difference between the two averages)
simple = LinearRegression().fit(X_train[["is_electronic"]], y_train)
print(f"\nelectronic only: intercept {simple.intercept_:.1f}, coefficient {simple.coef_[0]:.1f} days")

#predicted vs actual
el = X_test["is_electronic"] == 1
plt.figure(figsize=(6.2, 5.6))
plt.scatter(y_test[~el], pred[~el], s=14, alpha=0.6, color=BLUE, label="not electronic")
plt.scatter(y_test[el], pred[el], s=18, alpha=0.8, color=ORANGE, label="electronic")
plt.plot([0, 400], [0, 400], "k--", lw=1, label="perfect prediction")
plt.xlim(0, 400)
plt.ylim(0, 400)
plt.xlabel("actual lead time (days)")
plt.ylabel("predicted lead time (days)")
plt.title(f"Testing set: R² = {r2:.2f}, RMSE = {rmse:.0f} days")
plt.legend(fontsize=8)
plt.savefig(FIGS + "lr_pred_vs_actual.png", dpi=160, bbox_inches="tight")
plt.close()

#residuals
plt.figure(figsize=(6.5, 3.6))
plt.scatter(pred, y_test - pred, s=12, alpha=0.6, color=BLUE)
plt.axhline(0, color="k", lw=1)
plt.xlabel("predicted lead time (days)")
plt.ylabel("residual = actual - predicted")
plt.title("Residuals on the testing set")
plt.savefig(FIGS + "lr_residuals.png", dpi=160, bbox_inches="tight")
plt.close()

#coefficients: format features and venues
labels = {"is_electronic": "electronic event", "start_hour": "start 1 hour later",
          "fri_sat": "Friday or Saturday", "lineup_size": "1 more artist",
          "headliner_shows_log2": "headliner twice as busy", "days_out": "event 1 day later in the calendar"}
fmt = coef[NUMERIC].rename(labels)
ven = coef[venues.columns].sort_values()
ven.index = [short(c.replace("venue_", ""), 24) for c in ven.index]
fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.2]})
a.barh(fmt.index, fmt.values, color=[ORANGE if v < 0 else BLUE for v in fmt.values])
a.axvline(0, color="k", lw=0.8)
a.set_xlabel("change in lead time (days)")
a.set_title("Event features")
b.barh(ven.index, ven.values, color=[ORANGE if v < 0 else BLUE for v in ven.values])
b.axvline(0, color="k", lw=0.8)
b.set_xlabel("days compared with an 'other' venue")
b.set_title("Venues")
b.tick_params(axis="y", labelsize=8)
fig.tight_layout()
fig.savefig(FIGS + "lr_coefficients.png", dpi=160, bbox_inches="tight")
plt.close(fig)
