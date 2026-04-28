"""
Tests unitaires pour les parsers d'ingestion (Google, Spotify, etc.)
"""
import os
import shutil

import pytest

from src.ingestion.parsers.google import GoogleParser
from src.ingestion.parsers.spotify import SpotifyParser


@pytest.mark.unit
def test_google_parser_detect_and_move(mock_data_dirs):
    """Teste que le parser Google déplace correctement les fichiers Takeout avec ou sans sous-dossier 'Takeout'."""
    inbox, processed = mock_data_dirs

    # Simulation d'une archive Takeout standard (sans sous-dossier Takeout)
    archive1 = os.path.join(inbox, "takeout-20250101T120000Z-001")
    os.makedirs(os.path.join(archive1, "YouTube et YouTube Music", "historique"))
    with open(os.path.join(archive1, "YouTube et YouTube Music", "historique", "watch-history.html"), "w") as f:
        f.write("<html><body>Contenu factice 1</body></html>")

    # Simulation d'une archive Takeout avec le sous-dossier "Takeout"
    archive2 = os.path.join(inbox, "takeout-20250201T120000Z-002")
    os.makedirs(os.path.join(archive2, "Takeout", "Mon activité", "Recherche"))
    with open(os.path.join(archive2, "Takeout", "Mon activité", "Recherche", "MonActivité.html"), "w") as f:
        f.write("<html><body>Contenu factice 2</body></html>")

    parser = GoogleParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "GOOGLE")
    
    # Exécution du parser
    total_moved = parser.move()

    assert total_moved == 2, "Le parser aurait dû déplacer 2 fichiers"
    
    # Vérification de l'arborescence cible
    dest_yt = os.path.join(parser.dest, "YouTube et YouTube Music", "historique", "watch-history.html")
    dest_search = os.path.join(parser.dest, "Mon activité", "Recherche", "MonActivité.html")
    
    assert os.path.isfile(dest_yt), "Le fichier YouTube n'a pas été déplacé au bon endroit"
    assert os.path.isfile(dest_search), "Le fichier Recherche n'a pas été déplacé au bon endroit (gestion du sous-dossier Takeout défaillante)"


@pytest.mark.unit
def test_spotify_parser_routing(mock_data_dirs):
    """Teste que le parser Spotify route les fichiers dans les bons sous-dossiers (account vs extended)."""
    inbox, processed = mock_data_dirs

    # Archive 1 : Account Data
    acc_dir = os.path.join(inbox, "Spotify Account Data")
    os.makedirs(acc_dir)
    with open(os.path.join(acc_dir, "StreamingHistory_music_0.json"), "w") as f:
        f.write("[]")

    # Archive 2 : Extended Streaming History
    ext_dir = os.path.join(inbox, "Spotify Extended Streaming History")
    os.makedirs(ext_dir)
    with open(os.path.join(ext_dir, "Streaming_History_Audio_2020-2022_0.json"), "w") as f:
        f.write("[]")

    parser = SpotifyParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "SPOTIFY")
    
    total_moved = parser.move()

    assert total_moved == 2, "Le parser aurait dû déplacer 2 fichiers"

    # Vérification du routage
    assert os.path.isfile(os.path.join(parser.dest, "account", "StreamingHistory_music_0.json")), "Routage 'account data' défaillant"
    assert os.path.isfile(os.path.join(parser.dest, "extended", "Streaming_History_Audio_2020-2022_0.json")), "Routage 'extended' défaillant"
