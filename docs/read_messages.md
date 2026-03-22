# 📱 Guide — Lecteur de messages MyDigitalTwin

Bienvenue dans ce guide pour utiliser le lecteur de messages universel qui supporte **Instagram**, **Twitter/X** et **TikTok**.

---

## 🎯 Prérequis

- Tes données exportées depuis chaque plateforme (décompressées)
- Le fichier `message_reader.html`
- **Python** installé (pour afficher les médias correctement)

---

## 🚀 Étape 1 — Lancer le serveur local

Pour que les photos, vidéos et miniatures TikTok s'affichent correctement, il faut simuler un serveur web local.

**Windows :**
1. Ouvre l'Explorateur de fichiers dans le dossier `MyDigitalTwin/tools/`
2. Clique dans la barre d'adresse, tape `cmd` et appuie sur **Entrée**
3. Lance la commande :
   ```cmd
   python -m http.server 8000
   ```

**Mac / Linux :**
```bash
cd /chemin/vers/MyDigitalTwin/tools
python3 -m http.server 8000
```

> ⚠️ Laisse cette fenêtre ouverte pendant toute ta session de lecture.

4. Ouvre ton navigateur et va sur :
   👉 **`http://localhost:8000/message_reader.html`**

---

## 📸 Instagram

### Où trouver les fichiers
```
data/raw/INSTAGRAM/
└── your_instagram_activity/
    └── messages/
        └── inbox/
            └── nom_conversation/
                ├── message_1.json
                ├── message_2.json   ← (si la conv est longue)
                └── photos/
```

### Comment charger
1. Dans le lecteur, clique sur l'icône **📸** dans le rail gauche
2. Glisse-dépose le dossier `inbox/` entier **ou** sélectionne les fichiers `message_*.json` d'une conversation spécifique
3. Tes conversations apparaissent dans la sidebar à gauche

### Ce qui s'affiche
- 💬 Messages texte
- 📷 Photos (affichées directement)
- 🎥 Vidéos (avec lecteur intégré)
- 🎙️ Vocaux (avec lecteur audio)
- ❤️ Réactions emoji
- 🗑️ Messages supprimés (indiqués comme "Message supprimé")

---

## 🐦 Twitter / X

### Où trouver les fichiers
```
data/raw/X/
└── data/
    ├── direct-messages.js         ← DMs individuels
    └── direct-messages-group.js   ← DMs de groupe
```

### Comment charger
1. Clique sur l'icône **🐦** dans le rail gauche
2. Sélectionne `direct-messages.js` et/ou `direct-messages-group.js`
3. Tu peux charger les deux en même temps

### Ce qui s'affiche
- 💬 Messages texte
- 🔗 Liens sous forme de cartes cliquables
- 🖼️ Médias joints (si accessibles)

> 📝 Les noms de conversations affichent les derniers chiffres de l'ID utilisateur Twitter — les vrais noms ne sont pas inclus dans l'export.

---

## 🎵 TikTok

### Où trouver le fichier
```
data/raw/TIKTOK/
└── user_data_tiktok.json   ← tout est dans ce fichier (~35 Mo)
```

### Comment charger
1. Clique sur l'icône **🎵** dans le rail gauche
2. Sélectionne `user_data_tiktok.json`
3. Toutes tes conversations apparaissent automatiquement

### Ce qui s'affiche
- 💬 Messages texte
- 🎵 Vidéos TikTok partagées → carte avec miniature + clic pour ouvrir
- 🔗 Autres liens sous forme de cartes

> 💡 Les miniatures TikTok se chargent automatiquement via l'API publique TikTok. Si elles n'apparaissent pas, vérifie que tu es bien en ligne.

---

## 🔄 Charger plusieurs plateformes en même temps

Tu peux charger des conversations de toutes les plateformes dans la même session :
1. Charge Instagram → clique sur 📸 et glisse tes fichiers
2. Charge Twitter → clique sur 🐦 et glisse tes fichiers
3. Charge TikTok → clique sur 🎵 et glisse ton fichier

Le compteur sur chaque icône indique combien de conversations sont chargées par plateforme.

---

## 🔍 Rechercher une conversation

Utilise la barre de recherche en haut de la sidebar pour filtrer par nom de conversation.

---

## 🔐 Confidentialité

- **Tout reste local** — aucune donnée n'est envoyée sur internet
- Le seul appel réseau est vers l'API publique TikTok pour charger les miniatures des vidéos
- Tes fichiers JSON ne quittent jamais ton ordinateur

---

## ❓ Problèmes fréquents

| Problème | Solution |
|---|---|
| Les photos ne s'affichent pas | Lance le serveur Python et accède via `localhost:8000` |
| Les miniatures TikTok n'apparaissent pas | Vérifie ta connexion internet |
| "Message vide" s'affiche | Type de contenu non supporté (sticker, gif…) |
| Conversations Twitter avec des IDs | Normal — Twitter n'inclut pas les noms dans l'export |
| TikTok ne charge pas | Vérifie que le fichier s'appelle bien `user_data_tiktok.json` |