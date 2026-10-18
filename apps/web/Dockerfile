FROM node:24.22.0-trixie-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# A published container port reaches 0.0.0.0, not the loopback interface.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
