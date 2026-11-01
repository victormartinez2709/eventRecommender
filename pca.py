"""
Module 2: PCA tab.

    python pca.py      (after clustering.py, which gives the cluster colors)

PCA on the same standardized venue table used for clustering.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

FIGS = "assets/figures/pca/"
COLORS = ["#2a78d6", "#eda100", "#e87ba4", "#008300"]
MARKERS = ["o", "s", "^", "D"]

df = pd.read_csv("exports/module2/venue_features.csv")
clusters = pd.read_csv("exports/module2/cluster_assignments.csv")["kmeans_k4"]

#we scale the data to have mean = 0 and variance = 1
X = StandardScaler().fit_transform(df)
pd.DataFrame(X, columns=df.columns).round(4).to_csv("exports/module2/venue_features_standardized.csv", index=False)

#PCA with all 16 components
pca = PCA(random_state=42)
scores = pca.fit_transform(X)

#eigenvalues (variance of each PC) and how much of the total each one explains
eigenvalues = pca.explained_variance_
ratio = pca.explained_variance_ratio_
cum = np.cumsum(ratio)
print("eigenvalues:", np.round(eigenvalues, 3))
print("explained %:", np.round(100 * ratio, 1))
print("cumulative %:", np.round(100 * cum, 1))

#the same eigenvalues from the SVD of the centered data
U, S, Vt = np.linalg.svd(X - X.mean(axis=0), full_matrices=False)
print("from SVD:   ", np.round(S ** 2 / (len(X) - 1), 3))

#scree plot
pcs = np.arange(1, len(ratio) + 1)
plt.figure(figsize=(8, 3.8))
plt.bar(pcs, 100 * ratio, color=COLORS[0], label="each PC")
plt.plot(pcs, 100 * cum, marker="o", color="#eb6834", label="cumulative")
plt.axhline(80, color="grey", linestyle="--", linewidth=1)
plt.xticks(pcs, [f"PC{i}" for i in pcs], rotation=45)
plt.ylabel("% of variance explained")
plt.title("Scree plot")
plt.legend()
plt.savefig(FIGS + "scree_cumulative.png", dpi=160, bbox_inches="tight")
plt.close()

#loadings: the eigenvectors (weight of each variable in each PC)
loadings = pd.DataFrame(pca.components_[:3].T, index=df.columns, columns=["PC1", "PC2", "PC3"])
print("\n", loadings.round(2))

plt.figure(figsize=(5, 6.5))
plt.imshow(loadings, cmap="RdBu_r", vmin=-0.6, vmax=0.6, aspect="auto")
for i in range(loadings.shape[0]):
    for j in range(loadings.shape[1]):
        plt.text(j, i, f"{loadings.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
plt.xticks(range(3), [f"PC{j + 1} ({100 * ratio[j]:.0f}%)" for j in range(3)])
plt.yticks(range(len(df.columns)), df.columns)
plt.colorbar(label="loading")
plt.title("Loadings of each variable")
plt.savefig(FIGS + "loadings_heatmap.png", dpi=160, bbox_inches="tight")
plt.close()

#the venues on PC1 and PC2, coloured by k-means cluster (k = 4)
plt.figure(figsize=(8, 5.5))
for c in range(4):
    m = clusters == c
    plt.scatter(scores[m, 0], scores[m, 1], color=COLORS[c], marker=MARKERS[c], label=f"k-means cluster {c}")
plt.xlabel(f"PC1 ({100 * ratio[0]:.1f}%)")
plt.ylabel(f"PC2 ({100 * ratio[1]:.1f}%)")
plt.title("Venues on the first two principal components")
plt.legend()
plt.savefig(FIGS + "pc1_pc2_venues.png", dpi=160, bbox_inches="tight")
plt.close()
