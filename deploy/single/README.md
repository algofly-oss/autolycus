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
`AUTOLYCUS_SINGLE_IMAGE=registry.example/autolycus:latest`, then run
`docker compose -f compose.single.yml up -d --no-build`. Recipients need the
Compose file and the image, rather than a local source checkout/build toolchain.
The initial verified target is Linux amd64. The pinned Jackett artifact is amd64;
do not label this image as arm64 without adding and verifying matching artifacts.

## Direct movie playback

The public PWA can negotiate a WebRTC data channel with this container. Movie
bytes then travel directly between the viewer and the home machine when ICE
connectivity permits; login and signaling continue through the existing public
origin. If connectivity fails, bounded reads use the authenticated HTTP stream.
There is no TURN dependency: restrictive NAT/firewall combinations fall back to
the public route rather than allocating another relay.

Set `WEBRTC_CANDIDATE_HOSTS` in `.env` to comma-separated reachable IP addresses
of this machine (for example `192.168.1.20`). Compose publishes UDP 8555–8562 with
matching host/container port numbers. Home Wi-Fi needs to permit access to these
ports. For internet direct access, ICE/NAT traversal must succeed; a router UDP
forward can also make those ports reachable. No PortHub or URM2 change is needed.
The container's own interface address is included automatically. Keep advertised
addresses current if the machine uses DHCP. Set `WEBRTC_ENABLED=0` to use HTTP
only. Custom builds may change the internal `WEBRTC_UDP_PORT_START`, but published
ports must match. The existing HTTPS PWA URL stays unchanged. HTTP on a nonlocal
origin cannot use the service-worker bridge and uses normal HTTP playback.

The Rust byte service listens for control only on loopback. Python authenticates
each offer and renewal, binds a connection to the initiating login session, and
limits offers to 12/minute per session. Each peer can read only its already-open
file. A lease expires within 60 seconds without authenticated renewal. There are
at most eight peers, one pending read of at most 256 KiB per peer, and a 256 KiB
SCTP send window. No whole-file server buffer or streaming disk cache is created.
WebRTC adds encryption/transport work; this is not a zero-overhead transport.

Video.js 10 supplies the player. A black, square-cornered stage fills the window
immediately and keeps a stable height while metadata loads. One title and the
controls hide during playback. Audio, subtitles, speed, episodes and compatibility
options share the control-bar gear menu. On touch devices the opening tap requests
browser fullscreen where supported; otherwise the player fills the app window.
Left/right vertical swipes adjust in-player brightness/volume, side double taps
seek ten seconds, holding temporarily plays at 2×, and holding then dragging
previews a seek that is committed on release. Brightness does not alter the phone's
system setting. iOS volume restrictions use a client Web Audio gain fallback;
physical Safari/PWA testing is still required.

The episode queue lists videos from the starting directory and its subdirectories
in natural filename order, with previous/next buttons, selection in Settings →
Episodes, and an autoplay-next toggle. Discovery reads directory listings only,
never media contents, and is bounded to 64 folders, 8 levels and 500 videos.
Closing the player aborts discovery. Episode switching releases the previous
transport and client decoding resources. No server-side media processing is added.
Supported files retain native decoding;
the optional compatibility path uses Mediabunny on the viewer's device to demux
and remux encoded video without server conversion. Alternate audio selections
use that path. AC-3/E-AC-3 and DTS decoders and an AAC encoder load on demand when
required, and audio conversion runs on the client only. Unsupported HEVC has an
explicit **Play using this device** option. It loads a same-origin HEVC decoder
worker and converts video on the viewer's device; native-supported profiles keep
their original encoded video. Software playback may be slower, use more battery,
and change HDR colors. It does not promise realtime 4K decoding on every phone.
Client caches/buffers are bounded: 16 MiB of shared original-byte pages, 4 MiB in
the demuxer, a subtitle cue index limited to 2 MiB, and bounded playback lookahead. Video fragments are capped at 32 MiB;
unusually long keyframe intervals can require another playback version.
Seek operations cancel old packet pipelines. Sidecar `.vtt`/`.srt`
files named after the movie (including language suffixes) can be enabled or
disabled. Indexed MKV SubRip and ASS/SSA text tracks can also be selected, switched,
and disabled. Their text is read on the client using the same byte-page cache as
the movie. ASS styling is simplified; bitmap subtitles are not rendered. Cue
reads use bounded windows with a 30-second seek lookback and retain at most 200
native cues. Files without a usable bounded Matroska cue index retain sidecar or
native subtitle support. Other unsupported video codecs still depend on the device's decoder. Playback
never starts a server media transcode or remux. The separate thumbnail cache
may schedule low-priority FFmpeg keyframe sampling for existing videos.

The generated-media integration suite is `tests/single_container_playback.py`,
run with `/opt/flare-python/bin/python` inside a disposable smoke container. It
must not be run against production: it creates fixture users and media. Actual
iPhone Safari/PWA playback and Wi-Fi-to-cellular transitions also require device
testing; a narrow desktop viewport alone cannot verify those browser behaviors.

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

The storage gauge and percentage show **drive occupied / total drive capacity**
for every account. The compact hover shows drive used, total, and free bytes;
Autolycus's own footprint appears separately, without an adjusted capacity or
per-user quota. App usage is sampled outside request/progress paths, counting
hard links and overlapping mounts once.

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
docker build -t autolycus:latest .
python3 tests/single_container_smoke.py
```

The smoke test creates separate Docker volumes, uses randomly assigned loopback
web ports, and removes its fixtures by default. It tests the API, browser login,
TLS, Socket.IO, archive jobs, URL downloads, FTP transfer, FlareSolverr, Jackett,
restart persistence, and recovery after killing Redis. `--keep` retains fixtures
for inspection. Add `--live-tor` to verify that SOCKS, HTTP CONNECT, and browser
proxy traffic reach a Tor exit. Media-tool compatibility is checked with an
actual queued FFmpeg transcode. Tor bootstrap needs Internet access; local stack checks do not
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
docker build -t autolycus:latest .
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
continuous source search and `.torrent` metadata conversion.

## Media profiles and playback

Profiles are stored on the server; the browser stores only the active profile ID
under `autolycus:profile:<username>`. Profiles share downloads and account security,
but keep watch positions, audio/subtitle choices, quality, and view preferences
separate. Legacy history belongs to the default profile. The player writes its
file and timeline to the URL and saves progress on the server; file cards display
watch progress inside the card using the transcoding progress style; poster cards
keep a thin bottom bar. Episode queues use the existing Python PTN parser
and structured season/episode ordering. Existing public-link keys remain valid.

The player stays within the application's full-window black stage and requests
landscape fullscreen where the browser allows it. iPhone browsers can refuse
fullscreen/orientation locking; the player stays inline with custom controls and
a rotate hint. Physical iPhone gesture/orientation behavior requires device
verification. Audio language and subtitles are remembered per profile. Online
subtitle searches require a connection in Settings → Subtitles (OpenSubtitles
API key and, for account downloads, username/password). Credentials are encrypted
on the server; provider quotas still apply. Automatic selection requires an exact
provider movie-hash match when no suitable local subtitle exists.

The Audio menu can search the account's files and play another file's soundtrack
with the current video's original packets. Offset and independent audio speed
are saved per profile and movie. Auto align compares two bounded audio-energy
windows on the viewer's device, searches offsets within ±15 seconds, and stops
after roughly 55 seconds. It rejects
uncertain matches; different dubs, edits, intros, and ads may require manual sync.
Changing audio speed can change pitch. Audio decoding/AAC conversion runs on the
client, so compatibility depends on the device and may consume battery. No
playback-triggered server transcoding or alternate movie copies are created.

Auto quality starts with Original and switches conservatively among existing,
completed sibling variants only. Manual preferences survive episodes without the
chosen quality; missing options remain visible and disabled up to 2160p/4K.
Switches preserve playback position but can briefly reload the source. This is
not a seamless adaptive HLS ladder, and playback never creates missing versions.

## Explicit transcoding and preview budgets

Per-file transcoding from each file menu uses FFmpeg, with two simultaneous jobs by default
(`TRANSCODE_MAX_CONCURRENT`, maximum four), two threads per job
(`TRANSCODE_THREADS`), and three Celery worker processes. Queued jobs wait for a
slot; each file can be started or cancelled from its own menu. Completed outputs are
published atomically. HandBrake is no longer installed.

The base Compose file works without a GPU. To opt into NVIDIA NVENC with a
configured NVIDIA Container Toolkit/CDI host:

```sh
docker compose -f compose.single.yml -f compose.single.gpu.yml up -d --no-build
```

`NVIDIA_GPU_DEVICE` defaults to `nvidia.com/gpu=0`. The override sets
`TRANSCODE_USE_GPU=1`; explicit GPU mode reports an unavailable encoder instead of
silently consuming CPU. Concurrency, encoder surfaces, lookahead and CPU work are
bounded. These are workload limits, not a hard reservation or VRAM percentage cap;
other applications continue sharing the device.

Seek thumbnails live in MongoDB, not beside the movie. Completed downloads queue
both coarse PNG sheets and detailed TV JPEG sheets (about five seconds per frame,
up to 1,000 cells). A startup and five-minute API timer dispatches a server-side
catch-up scan of completed downloads. Each pass checks at most 128 videos and
queues at most eight missing sheets; a persistent cursor continues the next pass.
Cached, queued and temporarily failed variants are skipped. Symlinks and unfinished
downloads are excluded. No TV app needs to be open for this work.

Each sheet uses 160×90 cells and is capped at 5 MiB. The cache defaults to 512 MiB
(`MEDIA_PREVIEWS_CACHE_MB`, minimum 64) and expires unused entries after 30 days.
Very large libraries can evict old sheets; increase this budget if necessary.
One low-priority generator runs at a time and yields to playback and explicit
transcodes. Generation still uses CPU, RAM and disk I/O, and a new library takes
idle time to catch up. Set `MEDIA_PREVIEWS_ENABLED=0` to disable generation and
automatic scans. The cache is disposable; unavailable sheets can still be queued
on demand as a fallback.

Queue deduplication uses an atomic per-sheet Redis lease, renewed during long
generation, plus a shared renewable generator lock. Workers recheck MongoDB under
that lock before decoding, so repeated scans do not regenerate a completed sheet.
Deleting a file or download through Autolycus removes its cached sheets. The
five-minute scan also prunes sheets whose recorded source file no longer exists,
covering external deletion. Source paths remain internal server metadata and are
excluded from preview API responses.

HTTP(S) torrent tracker announces remain direct first. Repeated network failures
can retry through Tor; dead trackers, authorization errors, and rate limits do not
prove ISP blocking. UDP trackers and peer payload remain direct. This cannot
guarantee higher download speed. URL downloads use bounded aria2 connections,
verify TLS by default, handle nonzero exits, and monitor cancellation without
blocking on a quiet subprocess output stream.

## Shared video player

Copied public links use `/watch?key=…` directly and open the custom player without
requiring sign-in. Add `&download=true` (or `&download=1`) to download from that
address. Non-video shares open their original file. `/api/files/public/…` is used internally
for file bytes; it has no player redirect. `download=1` (or
`download=true`) takes precedence when supplied on the watch URL, even alongside `player=1`. The player includes
a Download action inside Settings: account playback uses the authenticated private file endpoint;
public playback uses that exact public share with `download=1`. Downloading a
private file does not activate a public link.

Guest playback is restricted to the active shared video and matching sidecar or
embedded subtitles. It does not list private folders, expose other episodes or
quality files, search another soundtrack, or use the owner's subtitle-service
credentials. Public WebRTC grants are bound to that share key and the same global
eight-peer budget; HTTP remains the fallback. Public seek previews only serve
already-generated cached sheets. Revoking the link rejects new requests and lease
renewals; already-established direct connections expire with their short lease.
Guest bookmarks stay in that browser, bounded to 32 shared files.

The control bar includes a direct Episodes list when a private queue has multiple
videos. Dismissing an open player menu consumes that tap instead of pausing the
movie. The Chromecast control is hidden when unavailable. The compact storage
hover shows overall drive occupancy as both a percentage and a thin bar.

The file browser has no selection checkboxes or bulk-transcode toolbar. Download
is inside the player Settings menu, rather than its top bar.

Settings uses PortHub’s workspace spacing, 190 px icon sidebar, mobile category grid,
rounded content surface, muted device rows, and labeled account/security forms.

Settings fields, action buttons, search/filter toolbar and section surfaces share
one scoped light/dark palette. The session search and filter align to the content
edge and stack at narrow widths. The profile switcher uses explicit theme data
because its portal lives outside the page wrapper; it shows the current profile
and links directly to the Profiles category. Category selection is URL-addressable.

## Cinema landing page

`/` is the authenticated streaming landing page; `/cinema` opens the same view.
Signed-out visitors go to the existing sign-in page, and successful login returns
to `/`. `/home` remains the management interface and has a Cinema link. Cinema
provides a featured title, Continue Watching, Movies/Series shelves, library-only
search, parsed episode selection and the existing private player without download
controls. Profiles and playback history remain account/profile scoped.

The catalog reads only the account's directory names and file stats. It reuses
cached metadata/posters, excludes unfinished torrents, samples and symlinks, and
collapses generated quality copies. Scans are bounded to 20,000 entries, 4,000
videos, depth 16 and three seconds; catalog results cache for 90 seconds (up to
4 MiB/account). A visible page refreshes on focus and every 90 seconds. Discovery
never starts video transcoding, thumbnail extraction or external poster searches.

Series and folder watch bars combine the fractional progress of each logical
video, including unwatched episodes. Alternate quality copies count once. This
uses episode/file shares rather than probing unwatched videos for their duration.
Folder inventories cache for 90 seconds and bars refresh after persisted bookmark
updates. Individual files keep their own timeline progress.

Seek-preview cells use cropped fill instead of generated black padding. The new
fingerprint regenerates older sheets on demand, retaining the same 100-cell,
5 MiB/sheet and 64 MiB total cache limits. Subtitle cues use modest responsive white
text with a shadow and transparent background. Quality menu lists scroll without
overlapping status text; Download has an inset scroll boundary and bottom spacing.
Matched cached episode artwork outranks an unmatched season-pack record.

### Online playback

Cinema title details offer **Watch now** alongside **Find in search**. Available
MP4 provider sources play in the existing custom player, with alternate editions
and resolutions under Settings → Source. Downloaded content still defaults to
Autolycus; Cinema's source menu can look up alternatives and return to the library
copy while preserving position, playback speed and paused state. Online playback
stores its current position in the address so refresh can reopen it.

The initial adapter uses MovieBox's guest API and matches catalog title, release
year and movie/series type. TV requests preserve explicit season/episode numbers;
there is no fallback from a missing episode to a movie. This adapter does not
promise every title, language, source website or codec. Provider URLs may expire
or become unavailable. No external iframe player is embedded.

This provider requires request headers unavailable to a browser video element,
so its media uses an authenticated, range-capable byte relay. The relay performs
no transcoding, decoding, media-file storage or whole-movie buffering. It uses
64 KiB chunks and eight stream slots per API process. Local-library LAN transport
is unchanged. Source URLs are opaque, account-bound and expire after two idle
hours. Source lookup caching is bounded independently of poster/metadata caches.
The protocol reference's MIT notice is in `api/third_party/Moviebox-API-LICENSE.txt`.

### Inspecting torrent contents

Search list rows include a folder action; poster cards offer **Browse files and
preview** in their menu. Opening it retrieves metadata without downloading file
payload. The dialog naturally sorts paths, filters filenames, previews videos
in the shared player and downloads only checked files. Selection survives native
restart and application pause/resume. Existing torrents are not silently replaced.

Previews reuse a lazy LibTorrentSession with four temporary leases (two/account),
80 connections, one disk-I/O thread and one hashing thread. Only requested pieces
and a small read-ahead window are prioritized. HTTP responses use at most 256 KiB
chunks; no server video decoding/transcoding is involved. Temporary sparse data
lives under hidden `/downloads/.previews`, expires after 15 idle minutes and is
removed when the file dialog closes. Aggregate preview transfer is limited to
8 MiB/s down and 256 KiB/s up, with a conservative 2 GiB data budget. Very large
pieces (over 32 MiB) are excluded from preview playback; metadata browsing and
selected download remain available. Preview peer connections are retained within
the connection limit while browsing, then disconnected on permanent-download
handoff. Normal download settings are unchanged.

Selective downloads currently require v1 or hybrid torrent metadata, matching
the existing download wrapper. Browser-only WebTorrent is not used: conventional
BitTorrent peers require the existing native engine, and most search results do
not guarantee WebRTC-capable peers. No separate torrent service is installed.

## Current release audit

See [RELEASE-VALIDATION.md](RELEASE-VALIDATION.md) for the final requirement audit,
archive import/fresh-boot proof, measured LAN startup and explicit provider/device
limits. [playback-validation.json](playback-validation.json) records the exact
shipping image and verified archive SHA-256.

## Public registration

`SIGNUP_DISABLED` follows PortHub's environment naming. It defaults to `false`
so a fresh installation can create its first account. Set `SIGNUP_DISABLED=true`
in `.env` and recreate the container to close registration:

```sh
docker compose -f compose.single.yml up -d --no-build
```

Use your existing GPU override too if that is how the installation was started.
The API returns 403 for every signup while disabled, including direct requests;
existing sign-in and sessions remain valid. The public, uncached
`/api/auth/settings` endpoint controls signup-link and signup-page visibility.
No first-account bypass or separate browser setting overrides the environment.
`true/yes/on/1` and `false/no/off/0` are accepted, case-insensitively; other values
fail configuration validation. Set it back to `false` and recreate to reopen.

The current maintained installation has registration disabled. Distribution
archives contain no installation `.env`; independent installations choose their
own setting. Sign-in/up fields are capped at 400px on laptops, following PortHub;
wallpaper copy is top aligned into the image's dark upper area.
