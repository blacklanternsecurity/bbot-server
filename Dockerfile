FROM python:3.11
COPY . /app
WORKDIR /app
# install bbot_server in editable mode
RUN pip install -e .
EXPOSE 8807
CMD ["bbctl", "server", "start", "--http-only"]
