# OpenClaw Docker Agent - Base Image
# Optimized for fast startup and layer caching

FROM node:18-slim

# Metadata
LABEL maintainer="OpenClaw"
LABEL description="Base image for OpenClaw Docker agents"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy package files first (for layer caching)
COPY package*.json ./

# Install dependencies
RUN npm install --production && npm cache clean --force

# Copy application code
COPY client.js task-executor.js health-monitor.js ./

# Create workspace directory
RUN mkdir -p /workspace && chmod 777 /workspace

# Set environment defaults
ENV NODE_ENV=production \
    AGENT_ID="" \
    AGENT_TOKEN="" \
    HUB_URL="ws://host.docker.internal:9090"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))" || exit 1

# Run as non-root user for security (use existing node user)
RUN chown -R node:node /app /workspace

USER node

# Start the agent
CMD ["node", "client.js"]
