FROM ghcr.io/astral-sh/uv:python3.11-trixie
RUN apt-get -y update && apt-get -y install curl jq
COPY . /app
WORKDIR /app
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8807
CMD ["uv", "run", "bbctl", "server", "start", "--api-only"]
