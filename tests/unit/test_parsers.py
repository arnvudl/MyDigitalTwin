"""
Tests unitaires pour les parsers d'ingestion (Google, Spotify, Netflix, Instagram, Twitter, TikTok).
"""
import os
import shutil
from unittest.mock import patch

import pytest

from src.ingestion.parsers.google import GoogleParser
from src.ingestion.parsers.instagram import InstagramParser
from src.ingestion.parsers.netflix import NetflixParser
from src.ingestion.parsers.spotify import SpotifyParser
from src.ingestion.parsers.tiktok import TikTokParser
from src.ingestion.parsers.twitter import TwitterParser


# ---------------------------------------------------------------------------
# GoogleParser
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_google_parser_detect_and_move(mock_data_dirs):
    """Teste que le parser Google déplace correctement les fichiers Takeout avec ou sans sous-dossier 'Takeout'."""
    inbox, processed = mock_data_dirs

    archive1 = os.path.join(inbox, "takeout-20250101T120000Z-001")
    os.makedirs(os.path.join(archive1, "YouTube et YouTube Music", "historique"))
    with open(os.path.join(archive1, "YouTube et YouTube Music", "historique", "watch-history.html"), "w") as f:
        f.write("<html><body>Contenu factice 1</body></html>")

    archive2 = os.path.join(inbox, "takeout-20250201T120000Z-002")
    os.makedirs(os.path.join(archive2, "Takeout", "Mon activité", "Recherche"))
    with open(os.path.join(archive2, "Takeout", "Mon activité", "Recherche", "MonActivité.html"), "w") as f:
        f.write("<html><body>Contenu factice 2</body></html>")

    parser = GoogleParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "GOOGLE")

    total_moved = parser.move()

    assert total_moved == 2
    assert os.path.isfile(os.path.join(parser.dest, "YouTube et YouTube Music", "historique", "watch-history.html"))
    assert os.path.isfile(os.path.join(parser.dest, "Mon activité", "Recherche", "MonActivité.html"))


# ---------------------------------------------------------------------------
# SpotifyParser
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_spotify_parser_routing(mock_data_dirs):
    """Teste que le parser Spotify route les fichiers dans les bons sous-dossiers (account vs extended)."""
    inbox, processed = mock_data_dirs

    acc_dir = os.path.join(inbox, "Spotify Account Data")
    os.makedirs(acc_dir)
    with open(os.path.join(acc_dir, "StreamingHistory_music_0.json"), "w") as f:
        f.write("[]")

    ext_dir = os.path.join(inbox, "Spotify Extended Streaming History")
    os.makedirs(ext_dir)
    with open(os.path.join(ext_dir, "Streaming_History_Audio_2020-2022_0.json"), "w") as f:
        f.write("[]")

    parser = SpotifyParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "SPOTIFY")

    total_moved = parser.move()

    assert total_moved == 2
    assert os.path.isfile(os.path.join(parser.dest, "account", "StreamingHistory_music_0.json"))
    assert os.path.isfile(os.path.join(parser.dest, "extended", "Streaming_History_Audio_2020-2022_0.json"))


@pytest.mark.unit
def test_spotify_parser_unknown_folder_falls_back_to_account(mock_data_dirs):
    """Un dossier Spotify non reconnu doit atterrir dans account/ (fallback)."""
    inbox, processed = mock_data_dirs

    unknown_dir = os.path.join(inbox, "Spotify Unknown Export")
    os.makedirs(unknown_dir)
    with open(os.path.join(unknown_dir, "some_file.json"), "w") as f:
        f.write("[]")

    parser = SpotifyParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "SPOTIFY")

    parser.move()

    assert os.path.isfile(os.path.join(parser.dest, "account", "some_file.json"))


# ---------------------------------------------------------------------------
# NetflixParser
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_netflix_parser_move(mock_data_dirs):
    """Teste que NetflixParser déplace le fichier CSV plat depuis la racine inbox."""
    inbox, processed = mock_data_dirs

    with open(os.path.join(inbox, "NetflixViewingHistory.csv"), "w") as f:
        f.write("Title,Date\nBlack Mirror S1,01/01/2023\n")

    parser = NetflixParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "NETFLIX")

    total = parser.move()

    assert total == 1
    assert os.path.isfile(os.path.join(parser.dest, "NetflixViewingHistory.csv"))


@pytest.mark.unit
def test_netflix_parser_returns_zero_when_no_file(mock_data_dirs):
    """Teste que NetflixParser retourne 0 si le CSV est absent."""
    inbox, processed = mock_data_dirs

    parser = NetflixParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "NETFLIX")

    assert parser.move() == 0


@pytest.mark.unit
def test_netflix_parser_run_prints_skip_message(mock_data_dirs):
    """Mock print pour vérifier le message de skip quand le CSV est absent."""
    inbox, processed = mock_data_dirs

    parser = NetflixParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "NETFLIX")

    with patch("builtins.print") as mock_print:
        result = parser.run()

    assert result == 0
    all_output = " ".join(str(c) for c in mock_print.call_args_list).lower()
    assert "skip" in all_output or "aucun" in all_output


@pytest.mark.unit
def test_netflix_parser_overwrites_existing(mock_data_dirs):
    """NetflixParser (OVERWRITE=True) doit remplacer un export précédent."""
    inbox, processed = mock_data_dirs

    dest_dir = os.path.join(processed, "NETFLIX")
    os.makedirs(dest_dir)
    with open(os.path.join(dest_dir, "NetflixViewingHistory.csv"), "w") as f:
        f.write("Title,Date\nOld Show,01/01/2022\n")

    with open(os.path.join(inbox, "NetflixViewingHistory.csv"), "w") as f:
        f.write("Title,Date\nNew Show,01/01/2023\n")

    parser = NetflixParser()
    parser.inbox = inbox
    parser.dest = dest_dir

    parser.move()

    with open(os.path.join(dest_dir, "NetflixViewingHistory.csv")) as f:
        content = f.read()
    assert "New Show" in content


# ---------------------------------------------------------------------------
# InstagramParser
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_instagram_parser_move(mock_data_dirs):
    """Teste que InstagramParser déplace les fichiers depuis inbox/instagram-*."""
    inbox, processed = mock_data_dirs

    ig_dir = os.path.join(inbox, "instagram-arnaud-20230101")
    os.makedirs(os.path.join(ig_dir, "your_instagram_activity", "likes"))
    with open(os.path.join(ig_dir, "your_instagram_activity", "likes", "liked_posts.json"), "w") as f:
        f.write("[]")

    parser = InstagramParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "INSTAGRAM")

    total = parser.move()

    assert total == 1
    assert os.path.isfile(
        os.path.join(parser.dest, "your_instagram_activity", "likes", "liked_posts.json")
    )


@pytest.mark.unit
def test_instagram_parser_preserves_existing_files(mock_data_dirs):
    """InstagramParser (OVERWRITE=False) ne doit pas écraser les fichiers déjà présents."""
    inbox, processed = mock_data_dirs

    dest_file = os.path.join(processed, "INSTAGRAM", "liked_posts.json")
    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
    with open(dest_file, "w") as f:
        f.write('["original"]')

    ig_dir = os.path.join(inbox, "instagram-arnaud-20230101")
    os.makedirs(ig_dir)
    with open(os.path.join(ig_dir, "liked_posts.json"), "w") as f:
        f.write('["new"]')

    parser = InstagramParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "INSTAGRAM")

    parser.move()

    with open(dest_file) as f:
        assert f.read() == '["original"]'


# ---------------------------------------------------------------------------
# TwitterParser
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_twitter_parser_move(mock_data_dirs):
    """Teste que TwitterParser déplace les fichiers .js depuis inbox/twitter-*."""
    inbox, processed = mock_data_dirs

    tw_dir = os.path.join(inbox, "twitter-20230101-export")
    os.makedirs(os.path.join(tw_dir, "data"))
    with open(os.path.join(tw_dir, "data", "tweets.js"), "w") as f:
        f.write("window.YTD.tweets.part0 = []")

    parser = TwitterParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "X")

    total = parser.move()

    assert total == 1
    assert os.path.isfile(os.path.join(parser.dest, "data", "tweets.js"))


@pytest.mark.unit
def test_twitter_parser_overwrites_existing(mock_data_dirs):
    """TwitterParser (OVERWRITE=True) doit remplacer les fichiers existants."""
    inbox, processed = mock_data_dirs

    dest_dir = os.path.join(processed, "X", "data")
    os.makedirs(dest_dir)
    with open(os.path.join(dest_dir, "tweets.js"), "w") as f:
        f.write("old_content")

    tw_dir = os.path.join(inbox, "twitter-20230101-export")
    os.makedirs(os.path.join(tw_dir, "data"))
    with open(os.path.join(tw_dir, "data", "tweets.js"), "w") as f:
        f.write("new_content")

    parser = TwitterParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "X")

    parser.move()

    with open(os.path.join(parser.dest, "data", "tweets.js")) as f:
        assert f.read() == "new_content"


# ---------------------------------------------------------------------------
# TikTokParser
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tiktok_parser_move(mock_data_dirs):
    """Teste que TikTokParser déplace user_data_tiktok.json depuis inbox/TikTok_Data_*."""
    inbox, processed = mock_data_dirs

    tiktok_dir = os.path.join(inbox, "TikTok_Data_20230101")
    os.makedirs(tiktok_dir)
    with open(os.path.join(tiktok_dir, "user_data_tiktok.json"), "w") as f:
        f.write("{}")

    parser = TikTokParser()
    parser.inbox = inbox
    parser.dest = os.path.join(processed, "TIKTOK")

    total = parser.move()

    assert total == 1
    assert os.path.isfile(os.path.join(parser.dest, "user_data_tiktok.json"))


@pytest.mark.unit
def test_tiktok_parser_overwrites_existing(mock_data_dirs):
    """TikTokParser (OVERWRITE=True) doit remplacer le fichier existant."""
    inbox, processed = mock_data_dirs

    dest_dir = os.path.join(processed, "TIKTOK")
    os.makedirs(dest_dir)
    with open(os.path.join(dest_dir, "user_data_tiktok.json"), "w") as f:
        f.write('{"old": true}')

    tiktok_dir = os.path.join(inbox, "TikTok_Data_20230201")
    os.makedirs(tiktok_dir)
    with open(os.path.join(tiktok_dir, "user_data_tiktok.json"), "w") as f:
        f.write('{"new": true}')

    parser = TikTokParser()
    parser.inbox = inbox
    parser.dest = dest_dir

    parser.move()

    with open(os.path.join(dest_dir, "user_data_tiktok.json")) as f:
        assert '"new": true' in f.read()
