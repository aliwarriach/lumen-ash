FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN useradd --create-home appuser
USER appuser

ENV PATH="/srv/.venv/bin:$PATH"

# Render sets $PORT. Migrations run on each start; they are a no-op when up to date.
# ONE process, on purpose: the community chat keeps its list of connected phones in memory
# (app/community/hub.py). Do not add --workers.
# --ws-max-size: the only things a phone sends over the chat socket are its login token and
# pings, so nothing bigger than 16 KB is accepted (the default allows 16 MB per frame).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --ws-max-size 16384"]
