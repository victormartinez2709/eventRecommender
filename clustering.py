"""
Module 2: Clustering tab.

    python clustering.py

k-means (elbow, silhouette, k = 3, 4, 5) and hierarchical clustering with
cosine distance on exports/module2/venue_features.csv.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

FIGS = "assets/figures/clustering/"
COLORS = ["#2a78d6", "#eda100", "#e87ba4", "#008300", "#e34948"]
MARKERS = ["o", "s", "^", "D", "v"]

#numeric, unlabeled data: one row per venue
Clustering = pd.read_csv("exports/module2/venue_features.csv")
#venue names are kept aside, only to read the results
names = pd.read_csv("exports/module2/venue_profiles_labeled.csv")["venue"]

#we scale the data to have mean = 0 and variance = 1
X = StandardScaler().fit_transform(Clustering)

#we reduce to 2 principal components only to plot the clusters
pca = PCA(n_components=2, random_state=42)
pca_vecs = pca.fit_transform(X)

# ---------------- elbow: WCSS for each value of k
inertia_score = []
for k in range(1, 11):
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    km.fit(X)
    inertia_score.append(km.inertia_)
print("WCSS:", np.round(inertia_score, 1))

plt.figure(figsize=(7, 3.6))
plt.plot(range(1, 11), inertia_score, marker="o", color=COLORS[0])
plt.xlabel("number of clusters k")
plt.ylabel("WCSS")
plt.title("Elbow Method")
plt.savefig(FIGS + "elbow.png", dpi=160, bbox_inches="tight")
plt.close()

# ---------------- silhouette: average score for each value of k
sil_score = []
for k in range(2, 11):
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    km.fit(X)
    sil_score.append(silhouette_score(X, km.labels_))
print("silhouette:", np.round(sil_score, 3))

plt.figure(figsize=(7, 3.6))
plt.plot(range(2, 11), sil_score, marker="o", color=COLORS[0])
plt.xlabel("number of clusters k")
plt.ylabel("average silhouette score")
plt.title("Silhouette Method")
plt.savefig(FIGS + "silhouette_by_k.png", dpi=160, bbox_inches="tight")
plt.close()

# ---------------- k-means with k = 3, 4 and 5
kmeans_labels = {}
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharex=True, sharey=True)
for ax, k in zip(axes, [3, 4, 5]):
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    km.fit(X)
    kmeans_labels[k] = km.labels_
    #we project the centroids onto PC1 and PC2 to plot them
    centers_2d = pca.transform(km.cluster_centers_)
    for c in range(k):
        m = km.labels_ == c
        ax.scatter(pca_vecs[m, 0], pca_vecs[m, 1], color=COLORS[c], marker=MARKERS[c],
                   label=f"cluster {c} ({m.sum()})")
    ax.scatter(centers_2d[:, 0], centers_2d[:, 1], color="k", marker="x", s=100, lw=2, label="centroid")
    ax.set_title(f"k = {k} (silhouette {silhouette_score(X, km.labels_):.2f})")
    ax.set_xlabel("PC1")
    ax.legend(fontsize=8)
    print(f"\nk = {k}")
    for c in range(k):
        print(f"  cluster {c}:", ", ".join(names[km.labels_ == c]))
axes[0].set_ylabel("PC2")
fig.savefig(FIGS + "kmeans_k3_k4_k5.png", dpi=160, bbox_inches="tight")
plt.close(fig)

#centroid of each cluster for k = 4, in the original units
Clustering["Cluster"] = kmeans_labels[4]
print("\n", Clustering.groupby("Cluster").mean().round(2).T)
Clustering = Clustering.drop(columns="Cluster")

# ---------------- hierarchical clustering with cosine distance
#average linkage (ward only works with Euclidean distance)
Z = linkage(X, method="average", metric="cosine")
print("\nheights of the last merges:", np.round(Z[-6:, 2], 3))

#we cut in the tallest gap between merges (0.93 -> 1.04)
CUT = 0.99
plt.figure(figsize=(12, 5.5))
dendrogram(Z, labels=names.tolist(), leaf_rotation=90, color_threshold=CUT)
plt.axhline(CUT, color="k", linestyle="--")
plt.ylabel("merge height (cosine distance)")
plt.title("Hierarchical clustering, cosine distance, average linkage")
plt.savefig(FIGS + "dendrogram_cosine.png", dpi=160, bbox_inches="tight")
plt.close()

hclust_labels = fcluster(Z, t=CUT, criterion="distance")
for c in sorted(set(hclust_labels)):
    print(f"  hclust group {c}:", ", ".join(names[hclust_labels == c]))

#how k-means (k = 4) and hierarchical clustering coincide
print("\n", pd.crosstab(kmeans_labels[4], hclust_labels, rownames=["k-means"], colnames=["hclust"]))

out = pd.DataFrame({"venue": names, "kmeans_k3": kmeans_labels[3], "kmeans_k4": kmeans_labels[4],
                    "kmeans_k5": kmeans_labels[5], "hclust": hclust_labels})
out.to_csv("exports/module2/cluster_assignments.csv", index=False)
