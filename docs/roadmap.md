# MyDigitalTwin — Roadmap ML & Dashboard
_Mis à jour : 2026-04-14_

---

## Vue d'ensemble

```
src/scripts/
├── 01_exploration/          ✅ Ingestion + nettoyage Delta Lake
├── 02_clustering/           ✅ K-Means comportemental (6 profils) → /profils
├── 06_social/               ✅ Graphe social (Instagram) → /social
├── 03_als/                  🔜 Recommandations ALS → /recommandations + /netflix + /spotify
├── 04_clone/                🚀 Pivot V5 (RAG + Gemini) → /clone (Fine-tuning archivé)
├── 07_psy/                  ✅ Analyse Comportementale Numérique → /psy
└── 05_CLIP/                 ⏳ Clustering photos CLIP → /photos  (après 10 mai)
```

---

## Statut des axes

### ✅ AXE 0 — Ingestion & exploration
**Dossier** : `01_exploration/`

- Lecture de toutes les sources brutes (Google, YouTube, Spotify, Netflix, Instagram, TikTok, X…)
- Nettoyage, normalisation, écriture en Delta Lake / Parquet
- Warehouse : `google_searches`, `youtube_watch`, `spotify_streams`, `netflix_views`, `google_chrome`, `tiktok_watch`, `instagram_likes`, `twitter_tweets`

---

### ✅ AXE 3 — Clustering comportemental K-Means
**Dossier** : `02_clustering/`  

- K-Means comportemental : k=6, features temporelles + plateforme.
- Dashboard : page `/profils` (cards + filtres + exemples par cluster).

---

### ✅ AXE social — Graphe social Instagram
**Dossier** : `06_social/`

- Analyse des interactions (messages 1-to-1) et pondération.
- Dashboard : page `/social` (Cytoscape graph).

---

### 🔜 AXE 2 — Recommandations ALS *(priorité haute)*
**Dossier** : `03_als/`  

**Objectif** : donner un titre → score "Arnaud aimera à X%"
- ALS implicite sur interactions Spotify + Netflix + YouTube.
- Dashboard : `/recommandations` (score + top suggestions) + `/netflix` + `/spotify`.

---

### 🚀 AXE 1 — Clone conversationnel (V5 : RAG + Gemini)
**Dossier** : `04_clone/`  
**Statut** : Pivot effectué (Fine-tuning archivé en V3 voir `STATUS.md`)

**Objectif** : Un clone qui imite le style (minimalisme, slang, rythme) sans hallucinations factuelles.
- **Moteur RAG** : Indexation sémantique (sentence-transformers) de 300 dialogues réels.
- **Inférence** : Gemini 1.5 Flash reçoit les 3 exemples les plus proches pour "injecter" le style dynamiquement.
- **Dashboard** : Page `/clone` avec chat interactif.

---

### ✅ AXE 5 — Analyse Comportementale Numérique
**Dossier** : `src/scripts/07_psy/`

**Objectif** : Générer un ZIP structuré (dossier comportemental + context éthique) à glisser-déposer dans un LLM pour une analyse de patterns numériques — **pas** un outil thérapeutique ou de psychanalyse clinique.

**Ce qui est livré :**
- Wizard 4 étapes sur `/psy` : période, sources, anonymisation, génération
- ZIP généré : `Analyse_Comportementale_XXXX.zip`
  - `DOSSIER_COMPORTEMENTAL.md` : stats dynamiques (messages, recherches, Spotify, Amazon)
  - `CONSIGNE_ANALYSTE.md` : posture "Digital Twin Analyst" (neutre, pas de diagnostic)
  - `context/` : fichiers statiques (`System_Prompt`, `Garde_Fous_Securite`, `Disclaimer`, `README`)
- Sources analysées : TikTok messages, Instagram messages (warehouse + fallback LLM_DATA), Google/YouTube searches, Spotify, Netflix, Amazon
- Anonymisation : remplacement des prénoms connus

**Note** : Pour inclure les conversations Instagram complètes, l'utilisateur doit les exporter depuis Instagram (Settings → Privacy → Download Your Information).

---

### ⏳ AXE 4 — Clustering photos CLIP *(après 10 mai)*
**Dossier** : `05_CLIP/`  

---

## Dashboard — état des pages

| Page | Statut | Source |
|---|---|---|
| `/` Home | ✅ Live | Delta Lake (Global scoring) |
| `/profils` | ✅ Live | K-Means comportemental |
| `/social` | ✅ Live | Instagram graph |
| `/psy` | ✅ Live | Analyse Comportementale Numérique (ZIP) |
| `/clone` | 🚀 V5 RAG | Gemini 1.5 Flash + RAG engine |
| `/netflix` | 🔜 AXE 2 | ALS scores |
| `/spotify` | 🔜 AXE 2 | ALS scores |
| `/recommandations` | 🔜 AXE 2 | ALS output |
| `/timeline` | ✅ Live | Vue agrégée (volume) |
| `/photos` | ⏳ Après 10 mai | CLIP clusters |
