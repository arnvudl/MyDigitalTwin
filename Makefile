.PHONY: install install-dev install-spark install-ml app freeze-app up down dev ingest ingest-parse-only

# ── Installation ──────────────────────────────────────────────────────────────
install:
	pip install -r requirements/app.txt

install-dev:
	pip install -r requirements/dev.txt

install-spark:
	pip install -r requirements/spark.txt

install-ml:
	pip install -r requirements/ml.txt --index-url https://download.pytorch.org/whl/cpu

# ── App locale ────────────────────────────────────────────────────────────────
app:
	python -m app.app

# ── Pinning (mettre à jour les versions après un pip install) ─────────────────
freeze-app:
	pip freeze | grep -E "^(dash|Flask|plotly|pandas|pyarrow|requests|python-dotenv|spotipy|google-genai)==" > requirements/app.txt
	@echo "✅  requirements/app.txt mis à jour"

# ── Ingestion GDPR ───────────────────────────────────────────────────────────
# Flux complet : inbox/ → raw/ → warehouse/  (overwrite)
ingest:
	python -m src.ingestion.run_all

# Re-parser raw/ sans déplacer inbox/ (utile après fix d'un parser)
ingest-parse-only:
	python -m src.ingestion.run_all --parse-only

# ── Docker ───────────────────────────────────────────────────────────────────
up:
	docker compose up -d --build

down:
	docker compose down --rmi all
	rm -rf data/output && rm -rf warehouse

dev:
	docker exec -it spark-master bash
