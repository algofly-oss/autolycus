FROM node:19.8.1-slim
RUN apt update -y && apt install -y bash vim && npm i -g nodemon pm2

WORKDIR /app
COPY package.json ./
COPY yarn.lock ./
RUN yarn install

COPY ./ ./
CMD chmod +x /app/entrypoint.sh && /app/entrypoint.sh