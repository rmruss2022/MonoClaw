FROM node:20-slim

WORKDIR /app

# Build tools needed for better-sqlite3 native module
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY package.json package-lock.json* ./

# Install deps with native rebuild
RUN npm install --build-from-source

# Copy source
COPY server.js ./
COPY lib/ ./lib/

# Data directory for SQLite (Railway volume or ephemeral)
RUN mkdir -p /data

ENV DB_PATH=/data/events.db
ENV NODE_ENV=production

EXPOSE 3000

CMD ["node", "server.js"]
