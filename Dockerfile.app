FROM python:3.11-slim

WORKDIR /app

# ── Dashboard deps uniquement (pas de torch/pyspark/ML lourd) ─────────────────
RUN pip install --no-cache-dir \
    dash==4.1.0 \
    dash-mantine-components==0.15.3 \
    dash-iconify==0.1.2 \
    Flask==3.1.3 \
    plotly==6.6.0 \
    pandas==3.0.2 \
    pyarrow==16.1.0 \
    requests==2.33.1 \
    python-dotenv==1.2.2 \
    pyyaml==6.0.2 \
    spotipy==2.26.0 \
    google-genai==1.73.1

# Copy application code
COPY app/ ./app/

# Expose the Dash port
EXPOSE 8050

# Run the Dash app
CMD ["python", "-m", "app.app"]
