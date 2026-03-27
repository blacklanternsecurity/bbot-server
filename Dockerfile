FROM ghcr.io/astral-sh/uv:python3.11-trixie
RUN apt-get -y update && apt-get -y install curl jq python3-pip pipx openssl tcpdump
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
RUN cp bbot_server/defaults_docker.yml bbot_server/defaults.yml
RUN uv sync --frozen
RUN useradd -u 1000 -m bbot && chown -R bbot:bbot /app
USER bbot
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8807
CMD ["uv", "run", "bbctl", "server", "start", "--api-only"]
