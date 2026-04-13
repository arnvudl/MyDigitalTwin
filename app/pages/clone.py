from dash import html, dcc, Input, Output, State, callback, ALL
import dash
import json
import os
from app.clone_utils import arnaud_rag

# ─── CONFIG ────────────────────────────────────────────────────────────────────
MODEL_NAME = "Gemini 1.5 Flash (RAG)"

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

    # Call Gemini RAG
    assistant_message = arnaud_rag.generate_response(user_input, history[:-1])

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
