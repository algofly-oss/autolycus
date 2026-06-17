FROM node:16-alpine AS builder

RUN apk add --no-cache git python3 make gcc musl-dev libc-dev g++
RUN git clone --depth 1 https://github.com/binary-person/womginx /opt/womginx

WORKDIR /opt/womginx
RUN rm -rf .git && git init

WORKDIR /opt/womginx/public
RUN rm -rf wombat && git submodule add https://github.com/webrecorder/wombat

WORKDIR /opt/womginx/public/wombat
RUN git checkout 78813ad
RUN npm install --legacy-peer-deps && npm run build-prod
RUN mv dist .. && rm -rf * .git && mv ../dist/ .

WORKDIR /opt/womginx
RUN ./docker-sed.sh
COPY patch-nginx.sh /tmp/patch-nginx.sh
RUN sh /tmp/patch-nginx.sh nginx.conf

FROM nginx:stable-alpine

RUN apk add --no-cache iptables redsocks

ENV PORT=80

COPY --from=builder /opt/womginx /opt/womginx
COPY redsocks.conf /etc/redsocks.conf
COPY entrypoint.sh /opt/womginx-tor-entrypoint.sh

RUN cp /opt/womginx/nginx.conf /etc/nginx/nginx.conf && nginx -t
RUN chmod +x /opt/womginx-tor-entrypoint.sh

CMD ["/opt/womginx-tor-entrypoint.sh"]
