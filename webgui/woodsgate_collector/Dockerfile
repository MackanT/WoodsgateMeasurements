FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Install system dependencies for building Python packages and I2C
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    i2c-tools \
    && rm -rf /var/lib/apt/lists/*

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy the project into the image
ADD . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Set environment variables
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["uv", "run", "collector"]