# Base image with Node.js
FROM node:20-alpine

WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY package*.json ./
RUN npm install --include=dev

# Copy application source
COPY . .

EXPOSE 3000
CMD ["npm","run","dev"]
