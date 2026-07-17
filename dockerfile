FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    iputils-ping \
    dnsutils \
    net-tools \
    vim \
    less \
    && rm -rf /var/lib/apt/lists/*

ENV HERMES_ENABLE_PROJECT_PLUGINS=true

WORKDIR /app
RUN curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

