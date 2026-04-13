import dash
from dash import html, dcc, Input, Output, State, callback, ALL
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
MODEL_NAME = "arnaud-clone"

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
def layout():
    return html.Div(className="page-wrapper", children=[
        html.Div(className="clone-container", children=[
            
            # Header
            html.Div(className="clone-header", children=[
                html.Div(className="clone-header-content", children=[
                    html.Div(className="clone-avatar", children=[
                        html.Img(src="/assets/CENTRE_INTERET.png"),
                    ]),
                    html.Div(className="clone-info", children=[
                        html.H2("Arnaud (Clone)", className="clone-name"),
                        html.Div(className="clone-status", children=[
                            html.Span(className="status-dot"),
                            html.Span(f"Modèle : {MODEL_NAME}", className="status-text")
                        ])
                    ])
                ])
            ]),

            # Chat History
            html.Div(id="chat-history", className="chat-history", children=[
                # Message initial
                html.Div(className="message-row assistant", children=[
                    html.Div(className="message-bubble", children=[
                        "salut, je suis ton jumeau numérique. on discute ?"
                    ])
                ])
            ]),

            # Input Area
            html.Div(className="chat-input-container", children=[
                dcc.Input(
                    id="chat-input",
                    type="text",
                    placeholder="Écris un message...",
                    autoFocus=True,
                    autoComplete="off",
                    className="chat-input"
                ),
                html.Button("Envoyer", id="chat-send", className="chat-send-btn")
            ]),
            
            # Hidden storage for history
            dcc.Store(id="chat-history-store", data=[
                {"role": "assistant", "content": "salut, je suis ton jumeau numérique. on discute ?"}
            ])
        ])
    ])

# ─── CALLBACKS ───────────────────────────────────────────────────────────────

@callback(
    Output("chat-history", "children"),
    Output("chat-history-store", "data"),
    Output("chat-input", "value"),
    Input("chat-send", "n_clicks"),
    Input("chat-input", "n_submit"),
    State("chat-input", "value"),
    State("chat-history-store", "data"),
    prevent_initial_call=True
)
def update_chat(n_clicks, n_submit, user_input, history):
    if not user_input or user_input.strip() == "":
        return dash.no_update, dash.no_update, ""

    # Append user message
    history.append({"role": "user", "content": user_input})

    # Call Ollama
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": history,
                "stream": False
            },
            timeout=30
        )
        if response.status_code == 200:
            assistant_message = response.json().get("message", {}).get("content", "Erreur de réponse Ollama")
        else:
            assistant_message = f"Erreur Ollama ({response.status_code}): {response.text}"
    except Exception as e:
        assistant_message = f"Erreur de connexion à Ollama : {str(e)}"

    # Append assistant message
    history.append({"role": "assistant", "content": assistant_message})

    # Create children for display
    children = []
    for msg in history:
        role_class = "user" if msg["role"] == "user" else "assistant"
        children.append(html.Div(className=f"message-row {role_class}", children=[
            html.Div(className="message-bubble", children=msg["content"])
        ]))

    return children, history, ""
