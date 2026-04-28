"""
Page /clone — Le Clone
Chat conversationnel propulsé par Gemini Flash + corpus de DMs réels.
"""

from google import genai
from google.genai import types
from dash import Input, Output, State, callback, dcc, html, no_update
from config import GEMINI_API_KEY, GEMINI_CORPUS_PATH, GEMINI_SYSPROMPT_PATH

# ─── PATHS ───────────────────────────────────────────────────────────────────
CORPUS_PATH = GEMINI_CORPUS_PATH
SYSPROMPT_PATH = GEMINI_SYSPROMPT_PATH

# ─── CHARGEMENT DU CORPUS (une seule fois au démarrage) ──────────────────────
def _load_text(path: str, label: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"[{label} introuvable — relancer 02_build_gemini_corpus.py]"

_CORPUS    = _load_text(CORPUS_PATH, "corpus")
_SYSPROMPT = _load_text(SYSPROMPT_PATH, "system prompt")

# System prompt complet injecté une seule fois : identité + corpus
_FULL_SYSTEM = f"""{_SYSPROMPT}

---

Voici des exemples réels de tes conversations passées. Imite ce style exactement.

{_CORPUS}
"""

# ─── GEMINI ──────────────────────────────────────────────────────────────────
_GEMINI_KEY = GEMINI_API_KEY
_gemini_client = genai.Client(api_key=_GEMINI_KEY) if _GEMINI_KEY else None

_GEMINI_CONFIG = types.GenerateContentConfig(
    system_instruction=_FULL_SYSTEM,
    # Le corpus injecté (~50k tokens) + historique dépasse rapidement
    # la limite free tier de 250k tokens/min sur Gemini 2.5 Flash.
    # Alternative : passer sur Groq (llama-3.3-70b, vraiment gratuit)
    # et réduire TOP_N dans 02_build_gemini_corpus.py de 300 → 50-100.
)


def _call_gemini(history: list[dict]) -> str:
    """Envoie l'historique complet à Gemini et retourne la réponse."""
    if not _gemini_client:
        return "[!] GEMINI_API_KEY manquante — définis la variable d'environnement."

    # Convertir l'historique Dash → format google.genai
    gemini_history = [
        types.Content(
            role="user" if msg["role"] == "user" else "model",
            parts=[types.Part(text=msg["content"])],
        )
        for msg in history[:-1]  # tout sauf le dernier (= message en cours)
    ]

    try:
        chat = _gemini_client.chats.create(
            model="gemini-2.5-flash",
            config=_GEMINI_CONFIG,
            history=gemini_history,
        )
        response = chat.send_message(history[-1]["content"])
        return response.text
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            return (
                "quota dépassé sur le free tier Gemini (250k tokens/min) — "
                "réessaie dans une minute ou passe sur Groq "
                "(llama-3.3-70b) avec TOP_N réduit à 50-100 dans 02_build_gemini_corpus.py"
            )
        return f"erreur Gemini : {e}"


# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    corpus_ok = os.path.exists(CORPUS_PATH)
    api_ok    = bool(_GEMINI_KEY)

    return html.Div(
        className="page-container",
        children=[
            dcc.Store(id="clone-history", data=[]),

            # En-tête
            html.Div(className="page-header", children=[
                html.H1("Le Clone", className="page-title"),
                html.P(
                    "Un clone conversationnel entraîné sur mes vrais DMs Instagram.",
                    className="page-subtitle",
                ),
            ]),

            # Alertes si config manquante
            html.Div([
                html.Div(
                    "[!] Corpus introuvable — lance src/scripts/04_clone/02_build_gemini_corpus.py",
                    className="clone-alert",
                ) if not corpus_ok else None,
                html.Div(
                    "[!] Variable GEMINI_API_KEY manquante",
                    className="clone-alert",
                ) if not api_ok else None,
            ]),

            # Zone de chat
            html.Div(className="clone-chat-wrapper", children=[

                # Fenêtre des messages
                html.Div(
                    id="clone-messages",
                    className="clone-messages",
                    children=[_welcome_bubble()],
                ),

                # Input bar
                html.Div(className="clone-input-bar", children=[
                    dcc.Input(
                        id="clone-input",
                        type="text",
                        placeholder="Écris un message…",
                        className="clone-input",
                        debounce=False,
                        n_submit=0,
                        autoComplete="off",
                    ),
                    html.Button(
                        "Envoyer",
                        id="clone-send",
                        className="clone-send-btn",
                        n_clicks=0,
                    ),
                ]),
            ]),
        ],
    )


def _welcome_bubble():
    return html.Div(className="clone-bubble clone-bubble--bot", children=[
        html.Span("bah wsh, c'est moi", className="clone-bubble-text"),
    ])


def _user_bubble(text: str) -> html.Div:
    return html.Div(className="clone-bubble clone-bubble--user", children=[
        html.Span(text, className="clone-bubble-text"),
    ])


def _bot_bubble(text: str) -> html.Div:
    # Gemini peut renvoyer des messages multi-lignes → on les split comme des rafales
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return html.Div(className="clone-bubble clone-bubble--bot", children=[
        html.Span(line, className="clone-bubble-text") for line in lines
    ])


# ─── CALLBACKS ───────────────────────────────────────────────────────────────
@callback(
    Output("clone-history",  "data"),
    Output("clone-messages", "children"),
    Output("clone-input",    "value"),
    Input("clone-send",  "n_clicks"),
    Input("clone-input", "n_submit"),
    State("clone-input",   "value"),
    State("clone-history", "data"),
    prevent_initial_call=True,
)
def on_send(n_clicks, n_submit, user_text, history):
    if not user_text or not user_text.strip():
        return no_update, no_update, no_update

    user_text = user_text.strip()

    # Ajouter le message utilisateur à l'historique
    history = history or []
    history.append({"role": "user", "content": user_text})

    # Appel Gemini
    bot_reply = _call_gemini(history)
    history.append({"role": "assistant", "content": bot_reply})

    # Reconstruire toute la liste de bulles
    bubbles = [_welcome_bubble()]
    for msg in history:
        if msg["role"] == "user":
            bubbles.append(_user_bubble(msg["content"]))
        else:
            bubbles.append(_bot_bubble(msg["content"]))

    return history, bubbles, ""
