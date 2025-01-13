FROM python:3.11
COPY . /app
WORKDIR /app
# install bbot_server in editable mode
RUN pip install -e .
# remove the initial app dir to avoid confusion
WORKDIR /
RUN rm -rf /app
# create new app dir (existing code will be mapped in)
RUN mkdir /app
WORKDIR /app
EXPOSE 8807
CMD ["python", "/app/bbot_server/cli/server.py"]
