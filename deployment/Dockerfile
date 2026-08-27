# syntax=docker/dockerfile:1
# ──────────────────────────────────────────────────────────────
# Application Streamlit — Impact Environnemental Alimentaire
#
# Build (depuis la RACINE du projet, pas depuis deployment/) :
#   docker build -f deployment/Dockerfile -t food-impact-app .
#
# Run :
#   docker run --rm -p 8501:8501 --env-file .env food-impact-app
#
# Avec la base locale du docker-compose, ajouter :
#   --network docker_default -e POSTGRES_HOST=food_impact_db
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libpq est requis par psycopg2-binary au runtime ; curl sert au healthcheck.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Les dépendances sont copiées seules d'abord : cette couche n'est réinvalidée
# que si requirements.txt change, pas à chaque modification du code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY models/ ./models/

# Utilisateur non-root
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app/streamlit_app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true", \
            "--browser.gatherUsageStats=false"]
