
FROM python:3.11-slim

ARG APP_VERSION=dev
ARG VCS_REF=local
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="email-service" \
			org.opencontainers.image.description="Transaction extraction API and workers" \
			org.opencontainers.image.version="$APP_VERSION" \
			org.opencontainers.image.revision="$VCS_REF" \
			org.opencontainers.image.created="$BUILD_DATE"

ENV PYTHONDONTWRITEBYTECODE=1 \
		PYTHONUNBUFFERED=1

SHELL ["/bin/sh", "-euxo", "pipefail", "-c"]

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root user for better container isolation.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app
USER appuser

# Use one image for multiple roles by setting APP_ROLE.
# APP_ROLE=api | poller | correlator
ENV APP_ROLE=api

EXPOSE 8000

CMD ["sh", "-c", "case \"$APP_ROLE\" in poller) python -m app.workers.poller_worker ;; correlator) python -m app.workers.correlator_worker ;; api|*) uvicorn app.main:app --host 0.0.0.0 --port 8000 ;; esac"]
