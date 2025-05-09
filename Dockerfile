FROM python:3.11
RUN apt-get -y update
RUN apt-get -y install curl jq
COPY . /app
WORKDIR /app
# install bbot_server in editable mode
RUN pip install -e .
EXPOSE 8807
CMD ["bbctl", "server", "start", "--api-only"]
