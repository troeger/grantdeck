FROM cgr.dev/chainguard/python:latest-dev AS builder

USER root
WORKDIR /app

COPY pyproject.toml manage.py ./
COPY apps ./apps
COPY grantdeck ./grantdeck
COPY deploy ./deploy

RUN pip install --no-cache-dir --prefix=/usr/local ".[docker]"

FROM cgr.dev/chainguard/python:latest

ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONPATH="/app:/usr/local/lib/python3.14/site-packages"

COPY --from=builder /usr/local /usr/local
COPY --from=builder --chown=65532:65532 /app /app

WORKDIR /app

EXPOSE 8000

ENTRYPOINT []
CMD ["python", "deploy/start.py"]
