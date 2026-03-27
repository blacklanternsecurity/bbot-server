FROM ghcr.io/astral-sh/uv:python3.11-trixie

WORKDIR /app

COPY . .

# run as much as possible in one layer to minimise the number of layers in, and susequent size of, the final image
RUN apt-get -y update && \
  apt-get -y install curl jq python3-pip pipx openssl tcpdump && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  uv sync --frozen --no-install-project && \
  cp bbot_server/defaults_docker.yml bbot_server/defaults.yml && \
  uv sync --frozen && \
  useradd -u 1000 -m bbot && chown -R bbot:bbot /app

USER bbot

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8807

CMD ["uv", "run", "bbctl", "server", "start", "--api-only"]
