import pandas as pd
import numpy as np
import os
import sys
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
import pyarrow.parquet as pq

# ── SETUP DES CHEMINS ────────────────────────────────────────────────────────
# On remonte de 2 niveaux (src/scripts/03_als -> MyDigitalTwin) pour config.py
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, ROOT_DIR)

try:
    from config import WAREHOUSE
except ImportError:
    print(f"❌ Erreur : Impossible d'importer config.py depuis {ROOT_DIR}")
    exit()

OUTPUT_PATH = os.path.join(WAREHOUSE, "movie_recommendations.parquet")
TMP_MATRIX_PATH = os.path.join(WAREHOUSE, "tmp_als_matrix")

print(f"🚀 Option C (SVD) - Root: {ROOT_DIR} - Warehouse: {WAREHOUSE}")

# 1. Chargement des données
print("📥 Chargement des interactions...")
if not os.path.exists(TMP_MATRIX_PATH):
    print(f"❌ Erreur : {TMP_MATRIX_PATH} introuvable. Relance la cellule 4 du notebook.")
    exit()

df = pd.read_parquet(TMP_MATRIX_PATH)

# 2. Préparation des IDs
print("📊 Préparation de la matrice...")
df['u_idx'] = df['userId'].astype("category").cat.codes
df['m_idx'] = df['movieId'].astype("category").cat.codes

user_map = dict(enumerate(df['userId'].astype("category").cat.categories))
movie_map = dict(enumerate(df['movieId'].astype("category").cat.categories))

# On cherche l'index d'Arnaud (userId=0)
try:
    arnaud_idx = list(user_map.values()).index(0)
except ValueError:
    print("❌ Erreur : Arnaud (userId 0) n'est pas dans la matrice.")
    exit()

# 3. Création de la Matrice Sparse
print("🏗️ Création de la matrice creuse...")
rating_matrix = csr_matrix((df['rating'].astype(np.float32), (df['u_idx'], df['m_idx'])))

# 4. Décomposition SVD
print(f"🧠 Calcul SVD (Rang 50) sur {df.shape[0]:,} interactions...")
u, s, vt = svds(rating_matrix, k=50)

# 5. Reconstruction des scores pour Arnaud
print("🎯 Génération des recommandations...")
s_diag_matrix = np.diag(s)
arnaud_scores = np.dot(np.dot(u[arnaud_idx, :], s_diag_matrix), vt)

# 6. Top 200
top_idx = np.argsort(arnaud_scores)[::-1][:200]

recos = pd.DataFrame({
    'movieId': [movie_map[i] for i in top_idx],
    'predicted_score': arnaud_scores[top_idx]
})

# 7. Enrichissement
print("📝 Enrichissement des métadonnées...")
movies = pd.read_parquet(os.path.join(WAREHOUSE, "movielens_movies"))
links = pd.read_parquet(os.path.join(WAREHOUSE, "movielens_links"))

final = recos.merge(movies[['movieId', 'title', 'genres']], on='movieId')
final = final.merge(links[['movieId', 'tmdbId']], on='movieId', how='left')

# Normalisation 0-100
s_min, s_max = final['predicted_score'].min(), final['predicted_score'].max()
final['predicted_score'] = ((final['predicted_score'] - s_min) / (s_max - s_min) * 100).round(1)
final['rank'] = range(1, len(final) + 1)

# 8. Sauvegarde
final.head(50).to_parquet(OUTPUT_PATH)
print(f"✅ Succès ! Recommandations écrites dans {OUTPUT_PATH}")

print("\n--- TES 10 MEILLEURES RECOMMANDATIONS ---")
print(final[['rank', 'title', 'predicted_score']].head(10).to_string(index=False))
