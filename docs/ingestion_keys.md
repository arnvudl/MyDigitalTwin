# Clés Primaires pour l'Ingestion Incrémentale (`MERGE INTO`)

Ce document liste les clés uniques logiques pour chaque table du warehouse.
L'objectif est d'utiliser ces clés pour exécuter des opérations `MERGE INTO` (upserts Delta)
plutôt que des `overwrite` complets, afin de gagner en temps d'exécution et de réduire les
opérations I/O coûteuses.

## Tables d'Ingestion (Niveau Silver -> Gold)

### Spotify
| Table | Source | Clé de Déduplication / Upsert | Remarques |
|---|---|---|---|
| `spotify_streams` | `StreamingHistory_music_*.json`<br>`Streaming_History_Audio_*.json` | `(artistName, trackName, date_trunc('minute', listen_ts))` | Les écoutes d'une même minute sont fusionnées en une seule. |
| `spotify_liked_songs` | `YourLibrary.json` | `trackUri` |
| `spotify_playlists` | `Playlist1.json` | `(playlistName, trackUri, addedDate)` |
| `spotify_searches` | `SearchQueries.json` | `(query, search_ts)` |

### Netflix
| Table | Source | Clé de Déduplication / Upsert | Remarques |
|---|---|---|---|
| `netflix_views` | `NetflixViewingHistory.csv` | `(raw_title, watch_date)` | Le titre brut inclut l'épisode, `watch_date` n'a qu'une précision à la journée. |

### Instagram
| Table | Source | Clé de Déduplication / Upsert | Remarques |
|---|---|---|---|
| `instagram_comments` | `post_comments_*.json` | `(text, timestamp)` |
| `instagram_likes` | `liked_posts.json` | `(post_url, timestamp)` |
| `instagram_saved` | `saved_posts.json` | `(post_href, timestamp)` |
| `instagram_messages_meta` | `message_*.json` | `(conv_id, sender_anon, timestamp_ms, msg_type)` |
| `instagram_searches` | `word_or_phrase_searches.json` | `(query, timestamp)` |
| `instagram_posts_viewed` | `posts_viewed.json` | `timestamp` | Action unitaire sans attribut. |
| `instagram_videos_watched` | `videos_watched.json` | `timestamp` | Action unitaire sans attribut. |
| `instagram_story_likes` | `story_likes.json` | `timestamp` | Action unitaire sans attribut. |

### TikTok
| Table | Source | Clé de Déduplication / Upsert | Remarques |
|---|---|---|---|
| `tiktok_watch` | `user_data_tiktok.json` | `(video_id, timestamp_ms)` |
| `tiktok_likes` | `user_data_tiktok.json` | `(video_id, timestamp_ms)` |
| `tiktok_saves` | `user_data_tiktok.json` | `(video_id, timestamp_ms)` |
| `tiktok_searches` | `user_data_tiktok.json` | `(query, timestamp_ms)` |
| `tiktok_comments` | `user_data_tiktok.json` | `(text, timestamp_ms)` |
| `tiktok_messages_meta` | `user_data_tiktok.json` | `(conv_id, sender_anon, timestamp_ms)` |
| `tiktok_messages_text` | `user_data_tiktok.json` | `(text, timestamp_ms)` |

### Twitter/X
| Table | Source | Clé de Déduplication / Upsert | Remarques |
|---|---|---|---|
| `twitter_tweets` | `tweets.js` | `tweet_id` | Clé primaire absolue fournie par l'API X. |
| `twitter_likes` | `like.js` | `tweet_id` |
| `twitter_saved_searches` | `saved-search.js` | `query` |

### Google & YouTube
| Table | Source | Clé de Déduplication / Upsert | Remarques |
|---|---|---|---|
| `google_searches` | `Recherche/MonActivité.html` | `(query, timestamp_ms)` |
| `google_chrome` | `Chrome/MonActivité.html` | `(url, timestamp_ms)` |
| `youtube_watch` | `watch-history.html` | `(video_id, timestamp_ms)` |
| `youtube_searches` | `Historique des recherches.html` | `(title, timestamp_ms)` | Titre contient la requête de recherche. |

## Implémentation du MERGE INTO

Dans les notebooks PySpark, l'opération de `MERGE` doit se faire via l'API Delta Lake.

**Exemple d'implémentation type :**

```python
from delta.tables import DeltaTable

# df_new : Nouveau DataFrame contenant le batch d'ingestion

delta_path = "path/to/warehouse/table_name"

if not DeltaTable.isDeltaTable(spark, delta_path):
    # Premier run : création de la table
    df_new.write.format("delta").save(delta_path)
else:
    # Runs suivants : Upsert
    deltaTable = DeltaTable.forPath(spark, delta_path)
    
    deltaTable.alias("target") \
      .merge(
        df_new.alias("source"),
        "target.key1 = source.key1 AND target.key2 = source.key2" # <- Voir les clés définies ci-dessus
      ) \
      .whenNotMatchedInsertAll() \
      .execute()
```