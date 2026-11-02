"""
Module 2: illustrations for the Overview sections and the Introduction.
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
steps = ["Listings\n(Ticketmaster,\nweekly)", "Clean events", "Venue profiles\n(16 numbers\nper venue)",
         "Clustering\n& PCA", "Recommend\nshows"]
plt.figure(figsize=(11, 2.2))
for i, s in enumerate(steps):
    color = BLUE if i in (2, 3) else "lightgrey"
    plt.text(i * 2.2, 0, s, ha="center", va="center", fontsize=12,
             bbox=dict(boxstyle="round,pad=0.6", fc="white", ec=color, lw=2))
    if i < len(steps) - 1:
        plt.text(i * 2.2 + 1.1, 0, "\u2192", ha="center", va="center", fontsize=18)
plt.xlim(-0.9, 9.7)
plt.ylim(-0.8, 0.8)
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
