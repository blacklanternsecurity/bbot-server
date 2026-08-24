FROM ghcr.io/astral-sh/uv:python3.11-trixie

WORKDIR /app

COPY . .

# run as much as possible in one layer to minimise the number of layers in, and susequent size of, the final image
RUN apt-get -y update && \
  apt-get -y install --no-install-recommends \
  # ensure sudo is available to install dependencies for containers operating as non-root agents
  sudo curl jq \
  && uv sync --frozen --no-install-project \
  && cp bbot_server/defaults_docker.yml bbot_server/defaults.yml \
  && uv sync --frozen \
  && useradd -u 1000 -m bbot \
  # ensure bbot user can run sudo without a password in order to install dependencies for containers operating as non-root agents
  && echo "bbot ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/bbot \
  && chown -R bbot:bbot /app

USER bbot

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8807

CMD ["uv", "run", "bbctl", "server", "start", "--api-only"]
