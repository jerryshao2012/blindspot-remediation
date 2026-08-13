# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Change Executor"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="Deterministic manual-patch ChangeExecutionService"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system executor \
    && useradd \
        --system \
        --gid executor \
        --create-home \
        --home-dir /home/executor \
        executor

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

# The shared-contracts package must be available from the organization's
# package feed or copied into the image build context. For local monorepo builds,
# install shared-contracts before installing this component.
RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work /artifacts \
    && chown -R executor:executor /app /work /artifacts /home/executor

USER executor
WORKDIR /work

ENTRYPOINT ["change-executor"]
