# syntax=docker/dockerfile:1.7
# One distributable runtime; build tools and SDKs stay in intermediate stages.
FROM rust:1.99.1-slim-bookworm AS rust-build
WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev pkg-config && rm -rf /var/lib/apt/lists/*
COPY runtime/Cargo.toml runtime/Cargo.lock ./
COPY runtime/src ./src
ENV CARGO_BUILD_JOBS=4 RUST_MIN_STACK=33554432
RUN --mount=type=cache,id=autolycus-cargo-registry,target=/usr/local/cargo/registry \
    --mount=type=cache,id=autolycus-cargo-target,target=/src/target \
    cargo clean --release -p autolycus-runtime && cargo build --locked --release && \
    cp target/release/autolycus-runtime /usr/local/bin/

FROM node:22-bookworm-slim AS ui-build
WORKDIR /src/ui
COPY ui/package.json ui/yarn.lock ./
RUN --mount=type=cache,id=autolycus-yarn,target=/usr/local/share/.cache/yarn \
    corepack enable && yarn install --frozen-lockfile --network-timeout 120000 --network-concurrency 4
COPY ui/ ./
ENV NEXT_TELEMETRY_DISABLED=1 AUTOLYCUS_STATIC_EXPORT=1
RUN yarn build && yarn next export --outdir /out/ui

FROM node:16-alpine AS womginx-build
ARG WOMGINX_REVISION=d11aecdb1f04f778c6fd769f5972101d95b2b73a
RUN apk add --no-cache git python3 make gcc musl-dev g++
RUN git clone https://github.com/binary-person/womginx /opt/womginx && \
    cd /opt/womginx && git checkout "$WOMGINX_REVISION" && rm -rf .git && git init
WORKDIR /opt/womginx/public
RUN rm -rf wombat && git submodule add https://github.com/webrecorder/wombat
WORKDIR /opt/womginx/public/wombat
RUN git checkout 78813ad && npm install --legacy-peer-deps && npm run build-prod && \
    mv dist .. && rm -rf * .git && mv ../dist/ .
WORKDIR /opt/womginx
COPY proxy/womginx-tor/patch-nginx.sh /tmp/patch-nginx.sh
RUN ./docker-sed.sh && sh /tmp/patch-nginx.sh nginx.conf && \
    rm -rf .git && sed -i 's/user nginx nginx;/user torbrowser torbrowser;/; s/listen 80;/listen 127.0.0.1:18080;/; s|pid /run/nginx.pid;|pid /run/womginx.pid;|; /include \/etc\/nginx\/conf.d/d; s/worker_processes auto;/worker_processes 1;/' nginx.conf

FROM mongo:5.0@sha256:41108d183e972dcbf98d09ed83f6cfc89a471a3f15d06f9d64a95e45d9db8dd2 AS mongodb
FROM getmeili/meilisearch:v1.10.0@sha256:77728dfc9daa3a28ffb857b267ab0f601cea1962d438af3c97c0b16988a65a46 AS meilisearch
FROM drakkan/sftpgo:v2@sha256:fd9ccdaada01c1c0674991aecbfea98f97d79313baffebcb8f708692d988bcbf AS sftpgo
FROM ghcr.io/flaresolverr/flaresolverr@sha256:7962759d99d7e125e108e0f5e7f3cdbcd36161776d058d1d9b7153b92ef1af9e AS flaresolverr
USER root
RUN rm -rf /app/chromedriver /app/__pycache__ /app/tests.py /app/tests_sites.py /app/build_package.py

FROM debian:trixie-slim AS jackett-build
ARG JACKETT_VERSION=v0.24.2977
ARG JACKETT_SHA256=0a5e8fa93cdd58539fe2aecd2a90ea4022f1838f1bed3f8e8d8c6d151f62a3a2
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && \
    curl -fsSL "https://github.com/Jackett/Jackett/releases/download/${JACKETT_VERSION}/Jackett.Binaries.LinuxAMDx64.tar.gz" -o /tmp/jackett.tar.gz && \
    echo "$JACKETT_SHA256  /tmp/jackett.tar.gz" | sha256sum -c - && \
    mkdir /out && tar -xzf /tmp/jackett.tar.gz -C /out && \
    find /out -name '*.pdb' -delete

FROM python:3.9-slim-trixie AS python-build
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libxml2-dev libxslt1-dev libffi-dev libpq-dev && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt /tmp/requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r /tmp/requirements.txt

FROM python:3.9-slim-trixie AS production
LABEL org.opencontainers.image.title="Autolycus" \
      org.opencontainers.image.description="Single-container production distribution: Rust, Python and Next.js"
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 BUILD_ENV=prod API_DEBUG=False \
    RUST_LOG=info,arti_client=warn,tor_=warn
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates tini nginx redis-server musl libgcc-s1 libcurl4t64 liblzma5 \
      libxml2 libxslt1.1 libffi8 libpq5 libicu76 libssl3t64 libgssapi-krb5-2 \
      ffmpeg handbrake-cli aria2 p7zip-full rsync \
      chromium chromium-driver xvfb xauth python3-venv iptables redsocks privoxy && \
    mkdir -p /usr/share/licenses/debian && \
    for file in /usr/share/doc/*/copyright; do \
      if [ -f "$file" ]; then cp -L "$file" "/usr/share/licenses/debian/$(basename "$(dirname "$file")").copyright"; fi; \
    done && \
    rm -rf /var/lib/apt/lists/* /usr/share/doc/* /usr/share/man/* /usr/share/locale/* && \
    useradd --uid 10001 --create-home --home-dir /data/home autolycus && \
    useradd --uid 10002 --no-create-home torbrowser && \
    mkdir -p /app /opt/ui /opt/flaresolverr /data /downloads /run/autolycus && \
    rm -f /etc/nginx/sites-enabled/default
ENV RAYON_NUM_THREADS=2
RUN --mount=type=bind,from=python-build,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index /wheels/*
COPY --from=flaresolverr /app /opt/flaresolverr
COPY --from=flaresolverr /package.json /opt/package.json
RUN /usr/bin/python3 -m venv /opt/flare-python && \
    /opt/flare-python/bin/pip install --no-cache-dir -r /opt/flaresolverr/requirements.txt && \
    rm -f /opt/flaresolverr/chromedriver && cp /usr/bin/chromedriver /opt/flaresolverr/chromedriver && \
    sed -i 's|/app/chromedriver|/opt/flaresolverr/chromedriver|g' /opt/flaresolverr/utils.py && \
    chown -R 10001:10001 /opt/flaresolverr
COPY --from=mongodb /usr/bin/mongod /usr/local/bin/mongod
# MongoDB 5 data compatibility; keep its legacy OpenSSL isolated from the OS.
COPY --from=mongodb /usr/lib/x86_64-linux-gnu/libssl.so.1.1 /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1 /opt/mongodb/lib/
COPY --from=meilisearch /bin/meilisearch /usr/local/bin/meilisearch
COPY --from=meilisearch /usr/lib/libgcc_s.so.1 /opt/meilisearch/lib/libgcc_s.so.1
COPY --from=sftpgo /usr/local/bin/sftpgo /usr/local/bin/sftpgo
COPY --from=sftpgo /usr/share/sftpgo /usr/share/sftpgo
COPY --from=jackett-build /out/Jackett /opt/jackett
COPY --from=ui-build /out/ui /opt/ui/
COPY --from=womginx-build /opt/womginx /opt/womginx
COPY --from=rust-build /usr/local/bin/autolycus-runtime /usr/local/bin/autolycus-runtime
COPY api /app
COPY proxy/nginx.conf /opt/autolycus/nginx.template
COPY deploy/single/bootstrap.py deploy/single/service.py deploy/single/healthcheck.py deploy/single/services.toml /opt/autolycus/
COPY LICENSE.txt /usr/share/licenses/autolycus/LICENSE.txt
RUN chown -R 10001:10001 /data /downloads /opt/ui && \
    ln -sf /dev/stdout /var/log/nginx/access.log && ln -sf /dev/stderr /var/log/nginx/error.log
WORKDIR /app
EXPOSE 80 443 2121 9118 50000-50100
VOLUME ["/data", "/downloads"]
HEALTHCHECK --interval=30s --timeout=15s --start-period=240s --retries=3 CMD ["python", "/opt/autolycus/healthcheck.py"]
ENTRYPOINT ["/usr/bin/tini", "--", "python", "/opt/autolycus/bootstrap.py"]
