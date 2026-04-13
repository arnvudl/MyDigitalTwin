import os
import re
import numpy as np
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_PATH = os.path.join(BASE_DIR, "data", "LLM_DATA", "gemini_corpus.txt")
SYSTEM_PATH = os.path.join(BASE_DIR, "data", "LLM_DATA", "gemini_system.txt")

# API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY and GOOGLE_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    genai.configure(api_key=GOOGLE_API_KEY)
    MODEL = genai.GenerativeModel('gemini-1.5-flash')
else:
    MODEL = None

# ─── RAG ENGINE ───────────────────────────────────────────────────────────────

class ArnaudRAG:
    def __init__(self):
        self.corpus_examples = []
        self.embeddings = None
        self.system_prompt = ""
        self.embed_model = None
        
        self._load_data()
        self._init_embeddings()

    def _load_data(self):
        # Load System Prompt
        if os.path.exists(SYSTEM_PATH):
            with open(SYSTEM_PATH, "r", encoding="utf-8") as f:
                self.system_prompt = f.read().strip()
        
        # Load Corpus
        if os.path.exists(CORPUS_PATH):
            with open(CORPUS_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                # Split by "--- Exemple X ---"
                examples = re.split(r"--- Exemple \d+ ---", content)
                self.corpus_examples = [ex.strip() for ex in examples if ex.strip() and "ARNAUD" not in ex]
        else:
            print(f"Warning: Corpus not found at {CORPUS_PATH}")

    def _init_embeddings(self):
        if not self.corpus_examples:
            return
            
        print("Initializing embeddings for RAG...")
        try:
            self.embed_model = SentenceTransformer('all-MiniLM-L6-v2')
            # On embed le texte complet de chaque exemple pour la recherche sémantique
            self.embeddings = self.embed_model.encode(self.corpus_examples, convert_to_numpy=True)
            print(f"Loaded {len(self.corpus_examples)} examples into RAG engine.")
        except Exception as e:
            print(f"Error initializing embeddings: {e}")

    def get_relevant_context(self, query, top_n=3):
        if self.embed_model is None or not self.corpus_examples:
            return ""
            
        query_embedding = self.embed_model.encode([query], convert_to_numpy=True)
        
        # Simple Cosine Similarity
        similarities = np.dot(self.embeddings, query_embedding.T).flatten()
        top_indices = np.argsort(similarities)[-top_n:][::-1]
        
        relevant_examples = [self.corpus_examples[i] for i in top_indices]
        
        context = "Voici quelques exemples de conversations passées d'Arnaud pour t'aider à imiter son style :\n\n"
        for i, ex in enumerate(relevant_examples, 1):
            context += f"--- Exemple de style {i} ---\n{ex}\n\n"
            
        return context

    def generate_response(self, user_input, chat_history):
        if not MODEL:
            return "Désolé, la clé API Gemini n'est pas configurée. Ajoute GOOGLE_API_KEY dans ton fichier .env."
            
        # 1. Get RAG context
        context = self.get_relevant_context(user_input)
        
        # 2. Build Prompt
        full_system_prompt = f"{self.system_prompt}\n\n{context}\nDirectives : Reste très court, utilise le slang d'Arnaud, pas de majuscules, sois spontané."
        
        # 3. Format history for Gemini
        messages = [{"role": "user", "parts": [full_system_prompt]}]
        
        # On ajoute l'historique récent (limité pour éviter de saturer)
        for msg in chat_history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            messages.append({"role": role, "parts": [msg["content"]]})
            
        # On ne rajoute pas user_input ici car il sera envoyé par le chat_session.send_message
        
        try:
            # On utilise le système prompt comme instruction de départ
            chat = MODEL.start_chat(history=messages[:-1])
            response = chat.send_message(user_input)
            return response.text
        except Exception as e:
            return f"Erreur Gemini : {str(e)}"

# Singleton instance
arnaud_rag = ArnaudRAG()
