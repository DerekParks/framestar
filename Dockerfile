FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-install-project
COPY framestar ./framestar
RUN uv sync --locked

ENV FRAMESTAR_CONFIG=/config/config.yaml
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "framestar"]
