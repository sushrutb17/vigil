FROM python:3.12-slim

WORKDIR /app

# Single-stage copy-then-install: pyproject declares explicit packages
# (agents, data, eval, pipeline, ui), so setuptools needs those directories
# present at install time. Splitting dependencies into an earlier layer would
# improve rebuild caching but fails the build outright.
#
# Exclusions come from TWO files that must be kept in sync, because they cover
# different tools: .dockerignore governs `docker build`, .gcloudignore governs
# `gcloud run deploy --source .`. Both exclude .env (live API key) and
# data/holdout (guardrail #3 — the locked holdout must never ship inside an
# image). Neither file protects the other tool's path, so do not delete one.
COPY . .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

ENV PORT=8080 \
    PYTHONUNBUFFERED=1
EXPOSE 8080

# Shell form so $PORT (set by Cloud Run) expands. headless=true suppresses the
# browser-open attempt and the first-run email prompt; XSRF protection is off
# because Cloud Run terminates TLS upstream and Streamlit otherwise rejects
# form posts from behind the proxy.
CMD streamlit run ui/streamlit_app.py \
    --server.address=0.0.0.0 \
    --server.port=$PORT \
    --server.headless=true \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
