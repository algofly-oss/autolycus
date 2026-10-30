# Single-container production deployment

Autolycus ships as one image and one running container. Python runs the API and
Celery jobs. Next.js builds the UI into static files served by Nginx; Node.js and
frontend dependencies are absent from the runtime. A stripped Rust executable
supervises services and embeds Arti 0.47 for Tor, following PortHub's approach.
MongoDB, Redis, Meilisearch, Jackett, FlareSolverr/Chromium, SFTPGo, Womginx,
redsocks, and Privoxy are bundled locally. No Docker socket or nested containers
are required.

## New installation

From the repository root:

```sh
docker compose -f compose.single.yml up -d --build
docker compose -f compose.single.yml ps
docker compose -f compose.single.yml logs -f --tail 100
```

Open `http://localhost:8089` or `https://localhost:4439`. The existing `.env` is
optional and controls published ports and public FTP settings. Without `.env`,
bootstrap generates unique credentials and a self-signed TLS certificate, saved
under `/data`. With `.env`, supply your own passwords instead of the example
values. Internal database/proxy addresses are always local to this container;
legacy Docker hostnames from `.env` are intentionally overridden.

For distribution, publish the image to your registry and set
`AUTOLYCUS_SINGLE_IMAGE=registry.example/autolycus:VERSION`, then run
`docker compose -f compose.single.yml up -d --no-build`. Recipients need the
Compose file and the image, rather than a local source checkout/build toolchain.
The initial verified target is Linux amd64. The pinned Jackett artifact is amd64;
do not label this image as arm64 without adding and verifying matching artifacts.

## Storage and configuration

| Setting / mount | Default | Purpose |
| --- | --- | --- |
| `AUTOLYCUS_DATA_PATH` → `/data` | `./volumes/single` | All databases, service config, Tor state, secrets, TLS |
| `DOWNLOADS_PATH` → `/downloads` | `./volumes/downloads` | Downloaded and generated files |
| `AUTOLYCUS_INSTALLATION_PATH` → `/installation` | Project directory | Read-only view for measuring all Autolycus files |
| `APP_HTTP_PORT` | `8089` | Web UI, API, Socket.IO, Tor browser |
| `APP_HTTPS_PORT` | `4439` | HTTPS with persisted certificate |
| `FTP_HOST_PORT` | `2121` | FTP control connection |
| `FTP_PASSIVE_PORT_START/END` | `50000` / `50100` | FTP passive data connections; map matching ports |
| `FTP_FORCE_PASSIVE_IP` | empty | Public server address when FTP is behind NAT |
| `JACKETT_HOST_PORT_MAP` | `9117` | Jackett management UI, published on host loopback only |
| `CELERY_NUM_WORKERS` | `2` | Parallel background jobs |
| `MONGO_CACHE_GB` | `0.25` | WiredTiger cache budget, in GB |
| `MEILI_MAX_INDEXING_MEMORY` | `256MiB` | Indexing memory budget |
| `MEILI_MAX_INDEXING_THREADS` | `2` | Indexing CPU concurrency |
| `MEILI_CPU_LIMIT` | `2` | CPUs available to Meilisearch, including its HTTP/scheduler pools |

Values in `.env` pass through to the container. Do not change database passwords
as a way to rotate credentials: environment changes do not alter existing users.
Preserve `/data/secrets.json`; losing the API key there prevents decrypting saved
FTP passwords. To use your own TLS identity, place both `server.crt` and
`server.key` under `/data/tls` before startup. Missing certificates are generated
on first boot. A partial certificate/key pair is rejected.

Login uses a persistent HttpOnly, SameSite=Lax cookie with a 30-day sliding
lifetime, matching HomeSense and controlled by `API_COOKIES_EXPIRE_MINUTES`
(default `43200`). Every
authenticated HTTP access renews both its browser lifetime and Redis TTL;
MongoDB is checkpointed hourly. Regular use maintains the session; more than
30 days of inactivity requires signing in again. Sessions
are recoverable from MongoDB if their Redis cache entry is lost; revoked and
expired sessions are rejected. `SESSION_COOKIE_SECURE=auto` sets Secure on HTTPS
requests. Set it to `true` when an HTTPS gateway terminates TLS before the local
proxy. Passwords and session tokens are not kept in frontend localStorage.

After updating an old home-screen installation, sign in once inside the installed
app if its previous session-only cookie has already been discarded. Subsequent
opens reuse the persistent cookie. Auth responses and API requests are excluded
from the service worker's cache. Temporary auth-network failures do not navigate
to login. Browser/private-mode data deletion or explicit logout still ends the
local session.

The storage gauge shows **Autolycus occupied / (drive capacity − space occupied
outside Autolycus)** for every user, including users with no files. It measures
allocated blocks across the installation, data and downloads on the downloads
drive, counting hard links and overlapping mounts once. The API samples usage
in the background every 60 seconds; HTTP and live updates read that shared
snapshot and current drive statistics. The UI refreshes every 30 seconds.

For an installation moved to an external data drive, set
`AUTOLYCUS_REQUIRE_EXISTING_DATA=1`. If its `/data/secrets.json` is unavailable,
startup fails rather than creating a blank installation on a missing mount.

Database and service endpoints bind to loopback. Web and FTP ports are published;
Nginx also proxies the Jackett management UI on a host-loopback-only port. Open
`http://localhost:9117` to configure indexers, or use an SSH tunnel for remote
administration. `NET_ADMIN` is used inside the container's network namespace to route
Womginx worker TCP sockets through redsocks and embedded Arti; it does not grant
host network access. Do not use `network_mode: host`. Other services' outbound
connections retain their existing routing. IPv6 TCP from Womginx is rejected.
Womginx still uses its configured external DNS resolver, matching the existing
implementation; the SOCKS endpoint itself supports remote hostname resolution.

Most bundled services run as UID 10001. The API, job worker, and SFTPGo retain the
existing root-based download ownership behavior for compatibility with current
download directories. Bootstrap changes ownership of service data, never the
downloads tree. The bind-mounted data directory becomes root:10001, mode 0750;
use `docker exec` or a root backup tool to inspect it.

## Migrate an existing installation

Build and test first, while the original containers remain running:

```sh
docker build -t autolycus:single .
python3 tests/single_container_smoke.py
```

The smoke test creates separate Docker volumes, uses randomly assigned loopback
web ports, and removes its fixtures by default. It tests the API, browser login,
TLS, Socket.IO, archive jobs, URL downloads, FTP transfer, FlareSolverr, Jackett,
restart persistence, and recovery after killing Redis. `--keep` retains fixtures
for inspection. Add `--live-tor` to verify that SOCKS, HTTP CONNECT, and browser
proxy traffic reach a Tor exit. Media-tool compatibility is checked with an
actual queued HandBrake transcode. Tor bootstrap needs Internet access; local stack checks do not
depend on an external website after bootstrap.

Schedule a brief write pause for the actual migration:

```sh
python3 deploy/single/migrate.py
```

The helper reads effective credentials from the original API, including its
legacy default encryption key, and records the original running containers. It
stops the original stack, copies MongoDB/Redis/Meilisearch/SFTPGo/Jackett state and
TLS into a **new empty** data directory, and starts the single container on the
existing ports. Downloads remain at the same bind mount and are not duplicated.
Original containers and database directories are retained. The helper compares
digests of user credentials, torrent identities, and existing sessions. If
startup or identity validation fails, it stops the replacement and restarts the
originals automatically. Saved Jackett Tor hostnames are translated to localhost.
On success, restart policies on the retained original containers are disabled
so they cannot start alongside the replacement after a host reboot. Their prior
policies are recorded in `/data/migration.json`.

The helper targets the current `autolycus_*` container names and bind mounts.
Take a separate backup before migrating a different topology. MongoDB 5 and
Meilisearch 1.10 are deliberately retained for on-disk compatibility. Upgrading
those databases is a separate migration. Redis may upgrade its persisted format
in the copied directory; the original copy remains unchanged. Redis retains the
existing RDB persistence policy (`save 20 1`); a forced crash can lose changes
since the most recent snapshot. A graceful stop saves current state.

To roll back immediately, before accepting new writes:

```sh
docker compose -f compose.single.yml down
docker update --restart=always autolycus_mongodb autolycus_redis autolycus_meilisearch autolycus_tor autolycus_flaresolverr autolycus_api autolycus_ui autolycus_jackett autolycus_womginx autolycus_ftp autolycus_proxy
docker start autolycus_mongodb autolycus_redis autolycus_meilisearch autolycus_tor autolycus_flaresolverr autolycus_api autolycus_ui autolycus_jackett autolycus_womginx autolycus_ftp autolycus_proxy
```

After accepting writes in the replacement, rolling back to the old database copy
would lose those new database changes. Reconcile/export them before rollback.

## Operations

Tini reaps orphaned children. The Rust supervisor launches commands directly,
isolates process groups, restarts failed services with bounded exponential
backoff, and sends TERM on shutdown with up to 60 seconds before KILL. Docker's
90-second stop grace period gives the supervisor time to finish. Docker health
checks verify the complete local stack, not only an HTTP liveness endpoint.
Docker reports unhealthy services; `restart: unless-stopped` restarts an exited
container, not a container that is merely unhealthy.

Update the image and recreate the container to upgrade. Jackett self-updates are
disabled so a release remains reviewable and repeatable. Persistent data stays
outside the image. Back up both mounts while the container is stopped:

```sh
docker compose -f compose.single.yml stop
# Back up AUTOLYCUS_DATA_PATH and DOWNLOADS_PATH with your backup tool.
docker compose -f compose.single.yml start
```

The build excludes local databases, downloads, credentials, TLS private keys,
node_modules, caches, and development output. Multistage builds leave Rust/Node
SDKs and C compilers outside the runtime. Chromium, codecs, and databases remain
the largest necessary components. CPU and memory depend on workload: media
transcoding, active browsers, and torrents can exceed idle measurements. Cache
and concurrency settings above are budgets, not a total container memory cap.

## Validation commands

```sh
cargo test --manifest-path runtime/Cargo.toml --locked
docker compose -f compose.single.yml config --quiet
docker build -t autolycus:single .
python3 tests/single_container_smoke.py
```

Runtime and deployment code live in `runtime/` and `deploy/single/`. The original
development Compose files and individual-service Dockerfiles remain usable.

See [the production validation report](VALIDATION.md) for measured image sizes,
resource samples, migration checks, and integration-test coverage. A local
distribution bundle is available in `dist/` after packaging:

```sh
docker load -i dist/autolycus-single-linux-amd64.tar.gz
docker compose -f dist/compose.single.yml up -d --no-build
```

The distribution example creates storage relative to the `dist/` directory.
Continue using the repository-root Compose file for the migrated installation.

See [search behavior and magnet resolution](SEARCH.md) for the title filter,
slower-source option and `.torrent` metadata conversion.
