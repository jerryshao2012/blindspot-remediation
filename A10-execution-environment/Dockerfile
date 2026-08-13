# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Execution Environment Service"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="Controlled sandbox execution gateway for AI engineering automation"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --system environmentservice \
    && useradd \
        --system \
        --gid environmentservice \
        --create-home \
        --home-dir /home/environmentservice \
        environmentservice

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN chown -R environmentservice:environmentservice \
    /app \
    /home/environmentservice

USER environmentservice

CMD [
    "python",
    "-c",
    "import execution_environment; print('Component 10 environment service image ready')"
]
