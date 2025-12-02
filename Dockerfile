# Crucible MCP Server - Docker Image
#
# Provides AI development verification infrastructure in a container.
#
# Build:   docker build -t crucible .
# Run:     docker run -it --rm -v crucible-data:/crucible/data crucible
#
# For Docker-in-Docker execution (isolated code runs):
#   docker run -it --rm \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -v crucible-data:/crucible/data \
#     crucible

FROM python:3.11-slim

LABEL maintainer="larro1991"
LABEL description="Crucible - AI Development Verification Infrastructure"
LABEL version="1.0"

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Create crucible user
RUN useradd -m -s /bin/bash crucible

# Set up working directory
WORKDIR /crucible

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=crucible:crucible . .

# Create data directories
RUN mkdir -p /crucible/data/memory \
             /crucible/fixtures \
             /crucible/learnings && \
    chown -R crucible:crucible /crucible

# Switch to crucible user
USER crucible

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CRUCIBLE_DATA_DIR=/crucible/data

# Expose port for potential HTTP transport
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from server.main import CrucibleServer; print('ok')" || exit 1

# Default command - stdio transport for MCP
ENTRYPOINT ["python", "-m", "server.main"]
CMD ["--transport", "stdio"]
