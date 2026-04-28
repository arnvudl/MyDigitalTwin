"""
Configuration globale de Pytest et fixtures partagées.
"""

import os
import shutil
import tempfile
import pytest

# On injecte le dossier courant (MyDigitalTwin) dans le path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import INBOX_ROOT, PROCESSED_DATA


@pytest.fixture
def mock_data_dirs(monkeypatch):
    """
    Crée des dossiers temporaires pour INBOX et PROCESSED
    et monkeypatche la configuration pour les utiliser.
    Nettoie après le test.
    """
    tmp_dir = tempfile.mkdtemp()
    mock_inbox = os.path.join(tmp_dir, "inbox")
    mock_processed = os.path.join(tmp_dir, "processed")
    
    os.makedirs(mock_inbox)
    os.makedirs(mock_processed)

    # Monkeypatching des variables de configuration
    import config
    import src.ingestion.base
    
    monkeypatch.setattr(config, "INBOX_ROOT", mock_inbox)
    monkeypatch.setattr(config, "PROCESSED_DATA", mock_processed)
    monkeypatch.setattr(src.ingestion.base, "INBOX_ROOT", mock_inbox)
    monkeypatch.setattr(src.ingestion.base, "PROCESSED_DATA", mock_processed)

    yield mock_inbox, mock_processed

    # Nettoyage
    shutil.rmtree(tmp_dir)
