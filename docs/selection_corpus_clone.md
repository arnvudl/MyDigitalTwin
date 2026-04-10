# Guide de Sélection & Préparation du Corpus (Clone)
_Objectif : Capturer l'essence d'Arnaud (le "vrai" lui)_

---

## 💎 La Philosophie "Keep the Noise"

Contrairement à un chatbot classique, nous ne cherchons pas à être poli ou efficace, mais à être **authentique**. Les messages dits "inutiles" sont en réalité les plus riches en **style**.

### ✅ Ce qu'il faut ABSOLUMENT garder :
- **Le Minimalisme** : "bah", "jsp", "oe", "nan", "t ou". C'est ta signature rythmique.
- **La Ponctuation & Casse** : Si tu n'utilises jamais de majuscules ou si tu mets des "..." partout, le dataset doit refléter ça.
- **Les Tics de Langage** : Tes expressions favorites, même les plus courtes.
- **Le Flow** : Si tu réponds souvent en 3 petits messages successifs au lieu d'un gros bloc, garde cette structure.

---

## 🛠 Méthode de Sélection "Hyper-Quali"

Le dataset final doit être un fichier `dataset.jsonl`. Pour chaque entrée, il nous faut du **contexte**.

### 1. Le Format (Instruction / Response)
Pour chaque message d'Arnaud, il faut le message précédent (l'ami) pour que le modèle comprenne le déclencheur.

**Exemple de ce qu'on veut :**
- **Ami** : "Tu viens ce soir ?"
- **Arnaud** : "bah oe jsp encore a quelle heure"

### 2. Gestion des messages courts (Le "Context" est clé)
Un "jsp" tout seul ne sert à rien au modèle. Il faut le lier à la question.

| Situation | Action |
|---|---|
| **Séquence de courts** | Fusionne-les ou garde la séquence si le format d'entraînement le permet. |
| **Humour / Sarcasme** | Garde absolument, même si c'est juste un emoji spécifique (ex: `💀` ou `😭`). |
| **Logistique pure** | Garde si la tournure est typique (ex: "j'arrive ds 5" vs "Je serai là dans cinq minutes"). |

---

## 📝 Format de Travail Manuel

Tu peux préparer un simple fichier texte ou Excel avant la conversion en JSONL.

**Structure recommandée :**
1. **Context** : (Optionnel) Ce qui se passait avant.
2. **L'Ami (Input)** : Le dernier message reçu.
3. **Arnaud (Output)** : Ta réponse exacte, brute, sans correction.

---

## 🚫 Ce qu'on filtre vraiment (Le vrai "poubelle")
- Les messages purement techniques : "Appel manqué", "Photo envoyée" (si on n'a pas la description), "Lien partagé" (sans commentaire).
- Les informations trop sensibles (codes, adresses précises, secrets d'état).
- Les doublons massifs (si tu as dit "ok" 4000 fois, on n'en garde que les 20 plus représentatifs avec des contextes variés).

---

## 💡 Conseil pour la "Data Augmentation"
Si tu trouves que tu n'as pas assez de messages sur un sujet (ex: ton avis sur un film), **écris-toi des fausses conversations**. 
Exemple : 
- Question : "T'en as pensé quoi de Dune 2 ?"
- Réponse : "incroyable la claque visuelle mais un peu long sur la fin nan ?"

**Qualité > Quantité : 500 exemples parfaits valent mieux que 10 000 messages bruités.**
