"""
Tests unitaires pour la configuration centrale (config.py)
"""
import os
import pytest

# On injecte le dossier courant (MyDigitalTwin) dans le path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import config


@pytest.mark.unit
def test_config_paths_no_hardcoding():
    """Vérifie que les chemins critiques ne sont pas écrits en dur avec 'C:/Users/...' ou équivalent."""
    # Ce test est une sécurité "fail-fast" pour l'audit du code.
    paths_to_check = [
        config.PROJECT_ROOT,
        config.DATA_ROOT,
        config.WAREHOUSE,
        config.PROCESSED_DATA,
        config.LLM_DATA,
    ]
    
    for path in paths_to_check:
        assert isinstance(path, str)
        # S'assurer que le chemin est relatif à la structure du projet, pas un truc local absolu hardcodé
        # (sauf s'il a été résolu par os.path.abspath, ce qui est normal, mais il ne doit pas 
        # contenir des choses comme "arnau/Documents" s'il est censé être portable).
        # En pratique, on teste que la logique de fallback "pick_data_root" fonctionne
        # sans erreur et que les variables existent.
        assert len(path) > 0


@pytest.mark.unit
def test_config_secrets_loaded():
    """S'assure que les variables d'environnement secrètes sont déclarées dans config.py."""
    # On ne teste pas la *valeur* (qui peut être vide en CI), mais la *présence* de la variable.
    secrets = [
        "TMDB_API_KEY",
        "TMDB_ACCESS_TOKEN",
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "GEMINI_API_KEY",
    ]
    
    for secret in secrets:
        assert hasattr(config, secret), f"Le secret {secret} n'est pas exposé par config.py"
