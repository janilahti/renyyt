FROM python:3.13-slim

ARG RENYYT_VERSION=dev
ARG VCS_REF=""
ARG BUILD_DATE=""

LABEL org.opencontainers.image.title="Renyyt" \
      org.opencontainers.image.version=$RENYYT_VERSION \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.created=$BUILD_DATE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RENYYT_HOST=0.0.0.0 \
    PORT=8787 \
    RENYYT_LOG_LEVEL=INFO

WORKDIR /app
COPY . /app
RUN python3 scripts/build.py \
    && addgroup --system renyyt \
    && adduser --system --ingroup renyyt --home /nonexistent --no-create-home renyyt \
    && chown -R renyyt:renyyt /app

USER renyyt

EXPOSE 8787
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import os, urllib.request; p=os.environ.get('RENYYT_BASE_PATH','').rstrip('/') + '/ready'; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('RENYYT_PORT',os.environ.get('PORT','8787')) + p, timeout=3).read()"

CMD ["python3", "run.py"]
