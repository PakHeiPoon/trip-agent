FROM python:3.12-slim

WORKDIR /app

# uv for fast, reproducible installs
RUN pip install --no-cache-dir uv

# Copy project (deps + source) and install with the optional HTTP server extra
COPY pyproject.toml uv.lock ./
COPY agent ./agent
COPY prompts ./prompts
COPY server.py ./
RUN uv sync --frozen --extra server --no-dev

EXPOSE 8000

# Env (VIVO_API_KEY etc.) is injected at runtime via `docker run --env-file .env`
CMD ["uv", "run", "--no-sync", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
