"""
Tests unitaires pour src/ingestion/base.py :
detect_source, scan_inbox, move_files.
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.ingestion.base import detect_source, move_files, scan_inbox


# ---------------------------------------------------------------------------
# detect_source
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("folder_name,expected", [
    ("instagram-arnaud-20230101",           "INSTAGRAM"),
    ("takeout-20230101T120000Z-001",        "GOOGLE"),
    ("TikTok_Data_20230101",               "TIKTOK"),
    ("twitter-20230101-export",             "X"),
    ("Spotify Account Data",               "SPOTIFY"),
    ("Spotify Extended Streaming History", "SPOTIFY"),
])
def test_detect_source_known_patterns(folder_name, expected):
    assert detect_source(folder_name) == expected


@pytest.mark.unit
@pytest.mark.parametrize("folder_name,expected", [
    ("INSTAGRAM-EXPORT",     "INSTAGRAM"),
    ("TAKEOUT-20230101",     "GOOGLE"),
    ("TIKTOK_DATA_2023",     "TIKTOK"),
    ("Twitter-20230101",     "X"),
    ("SPOTIFY ACCOUNT DATA", "SPOTIFY"),
])
def test_detect_source_case_insensitive(folder_name, expected):
    assert detect_source(folder_name) == expected


@pytest.mark.unit
@pytest.mark.parametrize("folder_name", [
    "my_random_folder",
    "NetflixViewingHistory",  # Netflix n'a pas de sous-dossier détectable
    "unknown_export",
    "photos_2023",
])
def test_detect_source_unknown_returns_none(folder_name):
    assert detect_source(folder_name) is None


# ---------------------------------------------------------------------------
# scan_inbox
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_scan_inbox_nonexistent_dir(tmp_path):
    result = scan_inbox(str(tmp_path / "nonexistent"))
    assert result == {}


@pytest.mark.unit
def test_scan_inbox_empty_dir(tmp_path):
    result = scan_inbox(str(tmp_path))
    assert result == {}


@pytest.mark.unit
def test_scan_inbox_ignores_files(tmp_path):
    (tmp_path / "instagram-export").mkdir()
    (tmp_path / "README.txt").write_text("ignored")

    result = scan_inbox(str(tmp_path))

    assert "INSTAGRAM" in result
    assert len(result["INSTAGRAM"]) == 1


@pytest.mark.unit
def test_scan_inbox_groups_multiple_sources(tmp_path):
    (tmp_path / "instagram-export").mkdir()
    (tmp_path / "takeout-20230101").mkdir()
    (tmp_path / "random_folder").mkdir()

    result = scan_inbox(str(tmp_path))

    assert set(result.keys()) == {"INSTAGRAM", "GOOGLE"}
    assert len(result["INSTAGRAM"]) == 1
    assert len(result["GOOGLE"]) == 1


@pytest.mark.unit
def test_scan_inbox_multiple_archives_same_source(tmp_path):
    (tmp_path / "takeout-20230101").mkdir()
    (tmp_path / "takeout-20230201").mkdir()

    result = scan_inbox(str(tmp_path))

    assert len(result["GOOGLE"]) == 2


# ---------------------------------------------------------------------------
# move_files
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_move_files_basic(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "file.txt").write_text("content")
    dst = tmp_path / "dst"

    moved = move_files(str(src), str(dst))

    assert moved == 1
    assert (dst / "file.txt").read_text() == "content"
    assert not (src / "file.txt").exists()


@pytest.mark.unit
def test_move_files_recursive(tmp_path):
    src = tmp_path / "src"
    (src / "sub" / "deep").mkdir(parents=True)
    (src / "sub" / "deep" / "file.txt").write_text("deep")
    dst = tmp_path / "dst"

    moved = move_files(str(src), str(dst))

    assert moved == 1
    assert (dst / "sub" / "deep" / "file.txt").read_text() == "deep"


@pytest.mark.unit
def test_move_files_preserves_existing_when_no_overwrite(tmp_path):
    """Invariant critique : overwrite=False ne doit JAMAIS écraser un fichier existant."""
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "file.txt").write_text("original")
    (src / "file.txt").write_text("new_content")

    moved = move_files(str(src), str(dst), overwrite=False)

    assert moved == 0
    assert (dst / "file.txt").read_text() == "original"


@pytest.mark.unit
def test_move_files_overwrites_when_flag_true(tmp_path):
    """overwrite=True doit remplacer le fichier existant (ex: Twitter, TikTok)."""
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "file.txt").write_text("original")
    (src / "file.txt").write_text("new_content")

    moved = move_files(str(src), str(dst), overwrite=True)

    assert moved == 1
    assert (dst / "file.txt").read_text() == "new_content"


@pytest.mark.unit
def test_move_files_calls_shutil_move_with_correct_args(tmp_path):
    """Mock shutil.move pour vérifier qu'il reçoit les bons chemins."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("x")
    dst = tmp_path / "dst"

    with patch("src.ingestion.base.shutil.move") as mock_move:
        move_files(str(src), str(dst), overwrite=True)

        assert mock_move.call_count == 1
        called_src, called_dst = mock_move.call_args[0]
        assert called_src.endswith("a.txt")
        assert "dst" in called_dst


@pytest.mark.unit
def test_move_files_no_overwrite_does_not_call_shutil_move(tmp_path):
    """Quand overwrite=False et que le fichier existe, shutil.move ne doit pas être appelé."""
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    (src / "file.txt").write_text("new")
    (dst / "file.txt").write_text("original")

    with patch("src.ingestion.base.shutil.move") as mock_move:
        move_files(str(src), str(dst), overwrite=False)

        mock_move.assert_not_called()
