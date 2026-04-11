import os
import json
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()

# Cache file path
CACHE_PATH = os.path.join("warehouse", "spotify_metadata.json")

class SpotifyMetadata:
    def __init__(self):
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        if client_id and client_secret:
            try:
                auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
                self.sp = spotipy.Spotify(auth_manager=auth_manager)
            except Exception:
                self.sp = None
        else:
            self.sp = None
            
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get_artist_image(self, artist_name):
        if not artist_name: return None
        cache_key = f"artist:{artist_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        if not self.sp: return None
        
        try:
            results = self.sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
            items = results.get("artists", {}).get("items", [])
            if items:
                img_url = items[0].get("images", [{}])[0].get("url")
                if img_url:
                    self.cache[cache_key] = img_url
                    self._save_cache()
                    return img_url
        except Exception:
            pass
        return None

    def get_track_image(self, track_name, artist_name):
        if not track_name or not artist_name: return None
        cache_key = f"track:{track_name}:{artist_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        if not self.sp: return None
        
        try:
            results = self.sp.search(q=f"track:{track_name} artist:{artist_name}", type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            if items:
                img_url = items[0].get("album", {}).get("images", [{}])[0].get("url")
                if img_url:
                    self.cache[cache_key] = img_url
                    self._save_cache()
                    return img_url
        except Exception:
            pass
        return None

# Singleton instance
spotify_meta = SpotifyMetadata()
