FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY bootstrap.py .
COPY tools/ tools/

EXPOSE 8000
CMD ["uvicorn", "bootstrap:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
