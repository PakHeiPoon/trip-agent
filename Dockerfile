FROM python:3.12-slim

WORKDIR /app

# uv for fast, reproducible installs
RUN pip install --no-cache-dir uv

# 1) deps only (cached layer — unchanged unless pyproject/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra server --no-dev --no-install-project
# 2) source + build the local package (fast; re-runs only when source changes)
COPY agent ./agent
COPY prompts ./prompts
COPY server.py ./
RUN uv sync --frozen --extra server --no-dev

EXPOSE 8000

# Env (VIVO_API_KEY etc.) is injected at runtime via `docker run --env-file .env`
CMD ["uv", "run", "--no-sync", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
