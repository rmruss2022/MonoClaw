FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --production

COPY src/ ./src/

RUN mkdir -p uploads

EXPOSE 3011

CMD ["node", "src/index.js"]
