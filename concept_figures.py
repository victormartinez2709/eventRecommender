"""
Modules 2-4: illustrations for the Overview sections and the Introduction.
They use small made-up data on purpose: they explain the methods.

    python concept_figures.py
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import AdaBoostClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier

BLUE, ORANGE = "#2a78d6", "#eb6834"
COLORS = ["#2a78d6", "#eda100", "#e87ba4"]


def save(path):
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()


#partitional vs hierarchical (Clustering, Figure 1)
rng = np.random.default_rng(7)
centers = np.array([[1, 1], [4.5, 1.5], [2.5, 4.5]])
P = np.vstack([c + rng.normal(0, 0.55, size=(7, 2)) for c in centers])
km = KMeans(n_clusters=3, n_init=10, random_state=42).fit(P)

fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4))
for c in range(3):
    a.scatter(P[km.labels_ == c, 0], P[km.labels_ == c, 1], color=COLORS[c])
a.scatter(km.cluster_centers_[:, 0], km.cluster_centers_[:, 1], color="k", marker="x", s=100, lw=2)
a.set_title("Partitional: k-means with k = 3")
b.set_title("Hierarchical: dendrogram of the same points")
dendrogram(linkage(P, method="average"), ax=b, no_labels=True)
b.set_ylabel("merge height")
save("assets/figures/clustering/concept_partitional_vs_hierarchical.png")

#distance metrics (Clustering, Figure 2)
A, B = np.array([4.0, 1.5]), np.array([1.5, 3.5])
euclid = np.sqrt(np.sum((A - B) ** 2))
manhattan = np.sum(np.abs(A - B))
cos_sim = np.dot(A, B) / (np.sqrt(np.sum(A ** 2)) * np.sqrt(np.sum(B ** 2)))

fig, axes = plt.subplots(1, 3, figsize=(11, 3.7), sharey=True)
for ax in axes:
    ax.annotate("", xy=A, xytext=(0, 0), arrowprops=dict(arrowstyle="->", color=BLUE, lw=2))
    ax.annotate("", xy=B, xytext=(0, 0), arrowprops=dict(arrowstyle="->", color=ORANGE, lw=2))
    ax.text(*A + 0.15, "A", color=BLUE, weight="bold")
    ax.text(*B + 0.15, "B", color=ORANGE, weight="bold")
    ax.set_xlim(-0.3, 5)
    ax.set_ylim(-0.3, 4.4)
axes[0].plot([A[0], B[0]], [A[1], B[1]], "k--")
axes[0].set_title(f"Euclidean = {euclid:.2f}")
axes[1].plot([A[0], B[0], B[0]], [A[1], A[1], B[1]], "k--")
axes[1].set_title(f"Manhattan = {manhattan:.2f}")
axes[2].set_title(f"Cosine similarity = {cos_sim:.2f}\n(only the angle matters)")
save("assets/figures/clustering/concept_distances.png")

#eigenvectors and eigenvalues (PCA, Figure 1)
x = rng.normal(0, 1, 120)
D = np.column_stack([x, 0.8 * x + rng.normal(0, 0.45, 120)])
D = D - D.mean(axis=0)
pca = PCA().fit(D)

plt.figure(figsize=(5.5, 4.8))
plt.scatter(D[:, 0], D[:, 1], s=14, color="#9ec5f4")
for i, col in enumerate([ORANGE, "k"]):
    v = pca.components_[i] * 2 * np.sqrt(pca.explained_variance_[i])
    plt.annotate("", xy=v, xytext=(0, 0), arrowprops=dict(arrowstyle="->", color=col, lw=2.5))
    plt.text(v[0] + 0.1, v[1] + 0.1, f"PC{i + 1}: eigenvalue {pca.explained_variance_[i]:.2f}\n"
             f"({100 * pca.explained_variance_ratio_[i]:.0f}% of variance)", color=col, fontsize=8)
plt.axis("equal")
plt.title("Eigenvectors = directions, eigenvalues = variance")
save("assets/figures/pca/concept_eigenvectors.png")

#projecting 2 columns onto 1 (PCA, Figure 2)
pca1 = PCA(n_components=1).fit(D)
back = pca1.inverse_transform(pca1.transform(D))
plt.figure(figsize=(5.5, 4.8))
for s, t in zip(D, back):
    plt.plot([s[0], t[0]], [s[1], t[1]], color="lightgrey")
plt.scatter(D[:, 0], D[:, 1], s=14, color=BLUE, label="original point (2 numbers)")
plt.scatter(back[:, 0], back[:, 1], s=10, color=ORANGE, label="projection on PC1 (1 number)")
plt.axis("equal")
plt.legend(fontsize=8)
plt.title(f"2 columns become 1, keeping {100 * pca1.explained_variance_ratio_[0]:.0f}% of the variance")
save("assets/figures/pca/concept_projection.png")

#the project pipeline (Introduction, Figure 2)
def box(x, y, text, color):
    plt.text(x, y, text, ha="center", va="center", fontsize=11,
             bbox=dict(boxstyle="round,pad=0.55", fc="white", ec=color, lw=2))


def arrow(x1, y1, x2, y2):
    plt.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color="grey", lw=1.5))


plt.figure(figsize=(12, 3.6))
box(0, 0, "Listings\n(Ticketmaster,\nevery 2 days)", "lightgrey")
box(2.2, 0, "Clean events", "lightgrey")
box(4.6, 0.9, "Venue profiles", "lightgrey")
box(7.2, 0.9, "Clustering & PCA:\nwhich venues\nprogram alike", "lightgrey")
box(4.6, -0.9, "Labeled events\n+ lead times", "lightgrey")
box(7.2, -0.55, "Naive Bayes, trees:\nis it electronic?", "lightgrey")
box(7.2, -1.45, "Regression, AdaBoost:\nelectronic? how early\non sale?", BLUE)
box(10, 0, "Recommend\nshows", "lightgrey")
arrow(0.75, 0, 1.45, 0)
arrow(2.95, 0.1, 3.75, 0.8)
arrow(2.95, -0.1, 3.75, -0.8)
arrow(5.45, 0.9, 6.05, 0.9)
arrow(5.6, -0.8, 6.0, -0.6)
arrow(5.6, -1.0, 5.95, -1.35)
arrow(8.35, 0.8, 9.35, 0.15)
arrow(8.35, -0.6, 9.35, -0.15)
arrow(8.5, -1.4, 9.4, -0.2)
plt.xlim(-0.9, 10.9)
plt.ylim(-2.0, 1.6)
plt.axis("off")
save("assets/figures/intro_pipeline.png")

#parts of a decision tree (Decision Trees, Figure 1)
nodes = {  # x, y, text, kind
    "root": (5, 4, "Starts after 8 pm?", "split"),
    "a": (2.5, 2.4, "On sale less than\n30 days ahead?", "split"),
    "b": (7.5, 2.4, "Leaf: electronic", "leaf"),
    "c": (1.2, 0.8, "Leaf: electronic", "leaf"),
    "d": (3.8, 0.8, "Leaf: not electronic", "leaf"),
}
edges = [("root", "a", "no"), ("root", "b", "yes"), ("a", "c", "yes"), ("a", "d", "no")]
plt.figure(figsize=(8, 4.2))
for p, c, lab in edges:
    (x1, y1), (x2, y2) = nodes[p][:2], nodes[c][:2]
    plt.plot([x1, x2], [y1 - 0.3, y2 + 0.3], color="grey")
    plt.text((x1 + x2) / 2, (y1 + y2) / 2, lab, ha="center", fontsize=9, color="grey",
             bbox=dict(fc="white", ec="none"))
for x, yy, text, kind in nodes.values():
    plt.text(x, yy, text, ha="center", va="center", fontsize=10,
             bbox=dict(boxstyle="round,pad=0.5", fc="#eaf0f8" if kind == "split" else "white",
                       ec=BLUE if kind == "split" else ORANGE, lw=1.5))
plt.text(9.3, 4, "root node", color=BLUE, fontsize=9)
plt.text(9.3, 1.2, "leaves\n(predictions)", color=ORANGE, fontsize=9)
plt.xlim(0, 10.5)
plt.ylim(0.2, 4.6)
plt.axis("off")
plt.title("A decision tree is a series of yes/no questions")
save("assets/figures/dectrees/concept_tree.png")

#Gini and entropy (Decision Trees, Figure 2)
p = np.linspace(0.001, 0.999, 200)
plt.figure(figsize=(6, 3.8))
plt.plot(p, 1 - p ** 2 - (1 - p) ** 2, color=BLUE, lw=2, label="Gini = 1 - p² - (1-p)²")
plt.plot(p, -p * np.log2(p) - (1 - p) * np.log2(1 - p), color=ORANGE, lw=2,
         label="Entropy = -p log₂p - (1-p) log₂(1-p)")
plt.xlabel("p = share of one class in a node")
plt.ylabel("impurity")
plt.title("Both are 0 for a pure node and highest at a 50/50 mix")
plt.legend(fontsize=8)
save("assets/figures/dectrees/concept_impurity.png")


#---------------------------------------------------------------- Module 4
#least squares (Regression, Figure 1): the five points from the Week 10 worksheet
xs = np.array([1, 2, 3, 4, 5])
ys = np.array([1, 3, 2, 5, 4])
line = LinearRegression().fit(xs.reshape(-1, 1), ys)
fit = line.predict(xs.reshape(-1, 1))
plt.figure(figsize=(6, 4.2))
for xi, yi, fi in zip(xs, ys, fit):
    plt.plot([xi, xi], [yi, fi], "--", color=ORANGE, lw=1.5)
grid = np.linspace(0.5, 5.5, 50)
plt.plot(grid, line.intercept_ + line.coef_[0] * grid, color=BLUE, lw=2,
         label=f"least-squares line  ŷ = {line.intercept_:.1f} + {line.coef_[0]:.1f}x")
plt.scatter(xs, ys, color="k", zorder=3, label="data")
plt.plot([], [], "--", color=ORANGE, label="residuals e = y - ŷ")
plt.xlabel("x")
plt.ylabel("y")
plt.legend(fontsize=8, loc="upper left")
plt.title("Linear regression: the line with the smallest sum of squared residuals", fontsize=10)
save("assets/figures/regression/concept_least_squares.png")

#a line vs the sigmoid on a yes/no label (Regression, Figure 2), made-up start times
hours = np.round(rng.uniform(17, 24, 80) * 2) / 2
p_true = 1 / (1 + np.exp(-1.6 * (hours - 20.8)))
yes = (rng.uniform(size=80) < p_true).astype(int)
H = hours.reshape(-1, 1)
lin = LinearRegression().fit(H, yes)
log = LogisticRegression(C=100).fit(H, yes)
g = np.linspace(15.5, 25.5, 200).reshape(-1, 1)
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax in (a, b):
    ax.scatter(hours, yes + rng.normal(0, 0.02, 80), s=14, color="grey", alpha=0.7)
    ax.axhline(0, color="lightgrey", lw=0.8)
    ax.axhline(1, color="lightgrey", lw=0.8)
    ax.set_xlabel("start hour (made-up data)")
a.plot(g, lin.predict(g), color=ORANGE, lw=2)
a.set_ylim(-0.35, 1.35)
a.set_ylabel("electronic?  (1 = yes, 0 = no)")
a.set_title("Linear regression: the line leaves [0, 1]")
z0 = -log.intercept_[0] / log.coef_[0][0]
b.plot(g, log.predict_proba(g)[:, 1], color=BLUE, lw=2)
b.axhline(0.5, color="k", ls="--", lw=1)
b.axvline(z0, color="k", ls=":", lw=1)
b.text(z0 + 0.15, 0.08, f"p = 0.5 at {z0:.1f}h\n(z = 0)", fontsize=8)
b.text(15.7, 0.56, "p ≥ 0.5: class 1", fontsize=8)
b.text(15.7, 0.40, "p < 0.5: class 0", fontsize=8)
b.set_title("Logistic regression: p = 1 / (1 + e^-z) stays in (0, 1)")
fig.tight_layout()
save("assets/figures/regression/concept_line_vs_sigmoid.png")

#bagging vs boosting (AdaBoost, Figure 1)
plt.figure(figsize=(12, 4.2))
plt.text(0.2, 3.6, "Bagging: trees in parallel, then a vote", fontsize=11, weight="bold")
for i in range(3):
    plt.text(0.6, 2.7 - i * 0.75, "random\nsample", ha="center", va="center", fontsize=8,
             bbox=dict(boxstyle="round", fc="white", ec="lightgrey"))
    plt.text(2.0, 2.7 - i * 0.75, "deep tree", ha="center", va="center", fontsize=9,
             bbox=dict(boxstyle="round", fc="white", ec="grey"))
    plt.annotate("", xy=(1.5, 2.7 - i * 0.75), xytext=(1.05, 2.7 - i * 0.75), arrowprops=dict(arrowstyle="->"))
    plt.annotate("", xy=(3.3, 1.95), xytext=(2.55, 2.7 - i * 0.75), arrowprops=dict(arrowstyle="->", color="grey"))
plt.text(3.75, 1.95, "equal\nvote", ha="center", va="center", fontsize=9,
         bbox=dict(boxstyle="round", fc="#eaf0f8", ec=BLUE))
plt.text(5.0, 3.6, "Boosting (AdaBoost): stumps one after another", fontsize=11, weight="bold")
for i in range(4):
    x = 5.5 + i * 1.45
    plt.text(x, 2.4, f"stump {i + 1}\nα{i + 1}", ha="center", va="center", fontsize=9,
             bbox=dict(boxstyle="round", fc="white", ec=ORANGE, lw=1.5))
    plt.scatter(x + rng.uniform(-0.35, 0.35, 8), 1.4 + rng.uniform(-0.2, 0.2, 8),
                s=[10 + 25 * i * v for v in rng.uniform(0, 1, 8)], color="grey")
    if i < 3:
        plt.annotate("", xy=(x + 0.95, 2.4), xytext=(x + 0.5, 2.4), arrowprops=dict(arrowstyle="->"))
        plt.text(x + 0.72, 2.75, "reweight", ha="center", fontsize=7, color="grey")
plt.text(7.7, 0.75, "dot size = weight of an event: the misses of one stump get heavier for the next",
         ha="center", fontsize=8, color="grey")
plt.annotate("", xy=(10.8, 2.4), xytext=(10.38, 2.4), arrowprops=dict(arrowstyle="->", color="grey"))
plt.text(11.35, 2.4, "weighted\nvote\nsign(Σ α h)", ha="center", va="center", fontsize=9,
         bbox=dict(boxstyle="round", fc="#eaf0f8", ec=BLUE))
plt.xlim(0, 12)
plt.ylim(0.5, 4)
plt.axis("off")
save("assets/figures/adaboost/concept_bagging_vs_boosting.png")

#AdaBoost round by round on made-up points (AdaBoost, Figure 2)
P1 = rng.normal([2, 2], 0.9, size=(14, 2))
P2 = rng.normal([3.6, 3.4], 0.9, size=(14, 2))
Q = np.vstack([P1, P2])
yq = np.array([-1] * 14 + [1] * 14)
wq = np.full(len(Q), 1 / len(Q))
fig, axes = plt.subplots(1, 4, figsize=(15, 4))
xx, yy = np.meshgrid(np.linspace(-0.5, 6.5, 200), np.linspace(-0.5, 6.5, 200))
grid2 = np.c_[xx.ravel(), yy.ravel()]
F = np.zeros(len(grid2))
for r in range(3):
    h = DecisionTreeClassifier(max_depth=1, random_state=0).fit(Q, yq, sample_weight=wq)
    hp = h.predict(Q)
    err = wq[hp != yq].sum()
    al = 0.5 * np.log((1 - err) / err)
    F += al * h.predict(grid2)
    ax = axes[r]
    ax.contourf(xx, yy, h.predict(grid2).reshape(xx.shape), levels=[-2, 0, 2], colors=["#d6e6fa", "#fbdccf"])
    ax.scatter(Q[:, 0], Q[:, 1], s=wq * 2500, c=[BLUE if v < 0 else ORANGE for v in yq],
               edgecolors=["k" if m else "none" for m in hp != yq], linewidths=1.5)
    ax.set_title(f"Round {r + 1}: error ε = {err:.2f}, α = {al:.2f}", fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    wq = wq * np.exp(-al * yq * hp)
    wq = wq / wq.sum()
axes[3].contourf(xx, yy, np.sign(F).reshape(xx.shape), levels=[-2, 0, 2], colors=["#d6e6fa", "#fbdccf"])
axes[3].scatter(Q[:, 0], Q[:, 1], s=40, c=[BLUE if v < 0 else ORANGE for v in yq])
axes[3].set_title("Final: sign(α1h1 + α2h2 + α3h3)", fontsize=10)
axes[3].set_xticks([])
axes[3].set_yticks([])
fig.suptitle("Dot size = the event's weight in that round; black ring = missed by that round's stump", fontsize=10)
fig.tight_layout()
save("assets/figures/adaboost/concept_rounds.png")

#the say of a stump (AdaBoost, Figure 3)
e = np.linspace(0.01, 0.6, 200)
plt.figure(figsize=(6, 3.6))
plt.plot(e, 0.5 * np.log((1 - e) / e), color=BLUE, lw=2)
plt.axhline(0, color="k", lw=0.8)
plt.axvline(0.5, color="grey", ls="--", lw=1)
plt.text(0.505, 1.4, "ε = 0.5:\ncoin flip,\nno say", fontsize=8)
plt.xlabel("weighted error ε of the stump")
plt.ylabel("α = ½ ln((1 - ε) / ε)")
plt.title("A stump's say in the final vote")
save("assets/figures/adaboost/concept_alpha.png")
