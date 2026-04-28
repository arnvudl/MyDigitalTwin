"""
Tests de qualité de données sur le warehouse (Delta Lake).
Ces tests vérifient que l'ingestion et les transformations se sont bien passées.
"""
import os
import pytest

from src.scripts.01_exploration.config import WAREHOUSE

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


@pytest.mark.data_quality
@pytest.mark.skipif(not HAS_PANDAS, reason="pandas n'est pas installé")
def test_netflix_views_quality():
    """Vérifie la qualité de la table netflix_views."""
    table_path = os.path.join(WAREHOUSE, "netflix_views")
    if not os.path.exists(table_path):
        pytest.skip(f"La table {table_path} n'existe pas (ingestion non exécutée).")

    df = pd.read_parquet(table_path)

    # 1. Volume minimal
    assert len(df) > 100, "La table Netflix semble anormalement vide (<100 lignes)."

    # 2. Invariants de schéma et de nullité
    assert "show_title" in df.columns, "La colonne 'show_title' est manquante."
    assert "watch_date" in df.columns, "La colonne 'watch_date' est manquante."
    assert df["show_title"].isnull().sum() == 0, "Des titres de séries/films sont nulls."
    assert df["watch_date"].isnull().sum() == 0, "Des dates de visionnage sont nulles."

    # 3. Logique métier
    assert "content_type" in df.columns
    types = df["content_type"].unique()
    assert set(types) <= {"series", "movie"}, f"Type de contenu inattendu trouvé : {types}"


@pytest.mark.data_quality
@pytest.mark.skipif(not HAS_PANDAS, reason="pandas n'est pas installé")
def test_spotify_streams_quality():
    """Vérifie la qualité de la table spotify_streams."""
    table_path = os.path.join(WAREHOUSE, "spotify_streams")
    if not os.path.exists(table_path):
        pytest.skip(f"La table {table_path} n'existe pas.")

    df = pd.read_parquet(table_path)

    assert len(df) > 1000, "La table Spotify semble anormalement vide."
    
    assert df["trackName"].isnull().sum() == 0, "Des noms de pistes sont nulls."
    assert df["artistName"].isnull().sum() == 0, "Des noms d'artistes sont nulls."
    assert df["listen_ts"].isnull().sum() == 0, "Des dates d'écoute sont nulles."

    # Invariant temporel : pas d'écoute dans le futur
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    # Les timestamps peuvent avoir une timezone ou non selon le format parquet, on normalise grossièrement
    # pour un test basique de qualité.
    max_date = pd.to_datetime(df["listen_ts"]).max().replace(tzinfo=None)
    
    # On laisse une marge d'une journée pour les problèmes de fuseau horaire lors de l'export
    margin = datetime.timedelta(days=1)
    assert max_date <= now + margin, f"Des dates d'écoute sont dans le futur : {max_date}"

    # Vérification du filtre > 30s
    assert (df["msPlayed"] >= 30000).all(), "Des écoutes de moins de 30 secondes sont présentes."
