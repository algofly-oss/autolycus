> Current release audit: [RELEASE-VALIDATION.md](RELEASE-VALIDATION.md).
> The chronological checkpoints below include superseded intermediate states.

# Production validation — updated 2026-10-31

The migrated deployment runs one healthy container,
`autolycus`, from `autolycus:latest`.

| Measurement | Result |
| --- | --- |
| Final image ID | `sha256:64cf8bc98070f64c7a175ca9d62d8c6f27de5fd5b2a7d4637c8b090f1cd25951` |
| Image content size reported by Docker inspect | 760,345,823 bytes |
| Existing eleven images, summed compressed content size | 1,863,404,306 bytes |
| Reduction in summed compressed image content | Approximately 59.1% |
| Docker CLI reported image size | 2.67 GB; original images summed to approximately 7.44 GB |
| Exported Docker archive | 756,080,096 bytes, approximately 721 MiB |
| Observed production memory sample | 539.3 MiB during live public playback |
| Observed production CPU sample | 0.59% of one CPU during that sample |

Summed old image sizes include any layers shared between those images; they are
not a measurement of unique disk space recovered. Idle samples are observations
after startup, not load benchmarks or peak-memory limits. Existing production
worker concurrency remains configurable through `.env`. No application-wide CPU
speedup is claimed from these samples.

## Verified behavior

- Rust unit tests: SOCKS negotiation/remote hostname handling, unsupported command
  rejection, supervisor configuration validation, child restart and cleanup.
- Rust Clippy passes with warnings denied. Python deployment/test files compile,
  Compose configuration validates, and `git diff --check` passes.
- Isolated integration checks pass for UI routes, HTTPS, Socket.IO handshake,
  signup/signin, MongoDB and Redis access, queued archive and media transcoding,
  real FTP login/file retrieval, queued URL download, file search, public file
  sharing, Chromium/FlareSolverr, Jackett, and complete-stack health.
- Chromium signs in through the UI, renders the authenticated home page, and
  survives a hard refresh without uncaught JavaScript or hydration errors.
- SOCKS, HTTP CONNECT, and the browser proxy each reach a verified Tor exit.
- Restart preserves data, secrets and the TLS identity. Killing Redis causes the
  Rust supervisor to replace it and the stack to recover.
- A seeded legacy-style Jackett Tor configuration is included in the smoke
  test. Its SOCKS bridge uses port 12345, while redsocks uses 12346.
- Migration preserves all **3 users, 32 torrent records, and 118 sessions**.
  Digests of credentials, torrent identities and session mappings match before
  and after migration and after recreating the production container.
- An existing migrated session authenticates and retrieves existing torrents
  through the production API. The production UI and Jackett management proxy
  respond successfully.
- The distribution archive passes SHA-256 verification and successfully imports
  with `docker load`.

The original containers and original service-data directories remain available
for rollback. Automatic restart of the originals is disabled to prevent two
deployments starting after a host reboot. Temporary integration containers and
their volumes have been removed.

## HDD relocation and follow-up fixes

The complete repository and all bind-mounted data now live at
`/mnt/WD8TB/autolycus`. `/mnt/WD512/autolycus` is a compatibility symlink; its
physical SSD copy has been removed after verification, freeing about 312 GiB.
Both production mounts explicitly resolve to the HDD. The relocated service
passes full-stack health checks and preserves the same 3 users, 32 torrents and
118 sessions.

Storage now reports actual drive usage and total capacity, shared by all users
over HTTP and Socket.IO, with deduplicated Autolycus usage as a separate value.
Hard links and overlapping mounts are counted once. Eleven additional
unit tests and full-stack checks pass for drive reporting and persistent
sessions. Browser process close/reopen restores login, and simulated auth-network
failure no longer redirects to sign-in. The selected policy matches HomeSense:
30 days, renewed on authenticated access. Logout and revocation remain effective.

See [storage and session details](STORAGE-AND-SESSIONS.md) and the machine-readable
`relocation-validation.json` (local-only, excluded from Git) for filesystem identity, byte counts and migration
identity digests. The refreshed archive contains these code changes.

## Distribution files

The local `dist/` directory contains the image archive, SHA-256 checksum,
`compose.single.yml`, and loading instructions. Load the archive and run Compose
with `--no-build` to deploy without Rust, Node.js, Python, or application sources
installed on the host. The verified image target is Linux amd64.

## Search quality and metadata resolution follow-up

The deployed image retains the visible, automatically filled second title filter.
Matching normalizes release separators and accents and preserves the selected
sort, with seeders descending by default. Zero or unknown seeder counts no longer
cause backend result loss. The slower-source checkbox has been removed. Searches wait for source completion
or failure, with user cancellation and periodic stream heartbeats.

Copy magnet and Download can resolve user-bound Jackett references, following
magnet responses or converting bounded `.torrent` metadata with libtorrent.
See [search behavior](SEARCH.md) for limits and failure behavior.

- All 21 Python unit tests pass, including generated `.torrent` conversion,
  redirects, download parameter preservation, response bounds, query retries,
  zero/unknown seeds, sessions and storage.
- Next.js production build and static export pass. JavaScript checks cover
  literal normalized title matching, seed order, valid hexadecimal/base32
  magnets, and rejection of invalid magnet values.
- The isolated API suite passes, including resolution-token ownership, expiry,
  input validation and authentication; the existing full-stack checks pass.
- Chromium verifies automatic title filtering, exclusion of unrelated titles,
  seed ordering, filtered-empty messaging, and Copy magnet through the real
  authenticated resolution API to a captured clipboard. Session close/reopen
  and temporary-network-loss checks also pass.
- Production recreation is healthy. All 3 users, 32 torrent records, 118 session
  mappings and their identity digests match before and after deployment.
- The refreshed distribution archive passes its SHA-256 check.

The checkbox-removal follow-up passes all 22 Python unit tests, including worker
cancellation and absence of an application read deadline. The Next.js build and
static export pass; the deployed image is healthy, contains no slower-source UI
label, and its refreshed distribution archive passes SHA-256 verification.

## Extensive title-filter tuning

See [live tuning measurements](search-validation.json) and [search behavior](SEARCH.md).
Sixteen bounded live Jackett metadata probes collected 17,886 raw rows across
language/genre keywords, old/new movies, title/year combinations, series/seasons,
year-only searches, and software/version names. The complete raw source stream
remains available; the automatically filled, editable secondary filter now uses
Fuse logical per-word queries plus a bounded word/version gate. No indexers or
proxy settings were changed and no model or runtime dependency was introduced.

All 52 curated cases and 20 substring negatives pass, including the full Fuse
pipeline and seed order. All 22 Python tests pass. The full isolated integration
suite passes before and after restart, including Redis recovery, session/browser
persistence and clipboard resolution. Browser fixtures explicitly confirm Hindi
excludes anime/HIDIVE lookalikes and Dune 2024 includes long multilingual titles
while excluding the wrong year. The deployment is healthy; users, torrents,
session mappings and identity digests match across recreation. The refreshed
archive passes SHA-256 verification. Temporary test containers/volumes were removed.

Counts reflect automated matching eligibility, not a human-labelled relevance
benchmark. Search coverage remains dependent on indexer availability and metadata;
keyword matching does not infer mood or genre absent from titles.

## Search acceleration and manual prefix filtering

The deployed matcher keeps strict automatic filtering but enables word prefixes
when users edit the second field. Both the full Fuse pipeline and Chromium verify
`m` → `mu` → `mus` keeps Musafir visible and a new search restores strict mode.
Search state tracks the manual mode alongside the existing query/filter state.

Faster, reliable sources run earlier based on persisted service-time/success
history. Repeated queries stream bounded recent source snapshots, then refresh
without duplicate rows; successful completion removes stale rows while errors
preserve only still-recent entries. All configured sources remain queued and the
existing Tor configuration and concurrency limit are unchanged.

All 30 Python tests pass, including cache expiry/scope/bounds, source history,
failed/empty refresh, cancellation and live fallback. JavaScript checks cover
manual prefixes, stale-row replacement and separate-source identities. The full
isolated integration/browser suite passes, including actual Redis Lua capacity
and TTL checks, restart persistence and Redis recovery. See
[controlled and production timing observations](search-speed-validation.json).
The production sample returned a first live Ubuntu row in 1,663.84 ms and a cached
repeat row in 8.68 ms; these are API observations, not whole-search or browser
latency guarantees. The production container is healthy and account, torrent and
session identity digests match across recreation. The refreshed archive passes
SHA-256 verification, and temporary test containers and volumes were removed.

## Account-synced search poster view — 2026-10-31

The search page adds a home-style list/thumbnail toggle, defaults to its existing
list view, and persists an independent search preference on the account. Cards
show cached movie/series posters, year/rating when available, release quality,
season/episode, seeders/size/source, and visible Copy magnet/Download/source/IMDb
controls. Lookup and image loading are lazy and deduplicated; no poster requests
are made in list mode. The cache-refresh message has been removed.

All 37 Python unit tests and JavaScript matching checks pass. The production
build/static export pass. Isolated integration and browser checks verify both
preferences persist through reload and a fresh browser, failed-save rollback,
authenticated poster delivery, release deduplication, clipboard copying, and
phone/tablet widths 320/375/390/414/768 including short 568/667px phone heights.
Both layouts have no horizontal overflow and retain access to bottom-row actions
above mobile navigation. Existing search/filter/session checks pass, and the
full-stack API suite passes before and after a container restart. React review
covered effect cleanup, request bounds/deduplication, virtualization, accessible
labels/pressed states, touch targets and failure handling. Existing lint warnings
remain; static poster images are intentionally served by the application's image
endpoint rather than requiring a Node/Next image runtime.

See [poster validation](search-posters-validation.json) and [search behavior](SEARCH.md).
The live production poster endpoint returns Dune: Part Two (2024) as an
approximately 38 KB same-origin image. The container is healthy and account,
torrent and session identity digests match across recreation. The refreshed
archive passes SHA-256 verification. Disposable test containers and volumes
were removed. Phone tests use viewport/touch emulation, not physical Safari.

## Home-style search visual alignment

Home and Search share one view-switch component. The search input and switch have
matching 48-pixel heights and aligned edges at every tested viewport. Search cards
reuse Home's neutral fallback and FileMenu, compact poster aspect/corners, bottom
gradient/title/metadata treatment and responsive 2/5/6/8-column density. The former
separate information panel and large colored Download button were removed; copy,
download, source/Tor and IMDb actions live in the shared menu. The menu remains
touch-accessible without hover. Resolution/quality and seeders/size occupy separate
compact lines to stay readable on narrow phones.

The isolated browser verifies menu copying, 44px menu items, bottom-row download
access above mobile navigation, switch alignment and horizontal containment across
320×568, 375×667, 390×844, 414×896 and 768×1024. Account preference restoration and
failed-save rollback pass. The full integration suite, restart and Redis recovery
checks pass; all 37 Python tests and JavaScript matching regressions pass. An
additional isolated visual review compared Home and Search using real poster
images at desktop and 320px phone size. OpenTabs was opened, but its production
browser was at sign-in; the user selected the isolated-browser alternative.

The deployed final image is healthy, user/torrent/session identity digests match,
and the updated distribution archive passes SHA-256 verification. Temporary test
containers and their volumes were removed. The OpenTabs daemon started for this
inspection was stopped and its temporary browser tabs were closed.

## Poster aliases and bounded LRU image cache

The separator now uses the same border class as the existing filter divider;
computed colors match in both light and dark themes at all tested viewports.
The minimal secondary-field control and Home-style cards remain in place.

Poster lookup strips release AKA annotations, normalizes acronym/bilingual title
forms, tolerates a tightly bounded spelling difference, and checks provider-listed
original/alternate titles and release years for renamed or festival/theatrical
variants. It does not blindly accept a nearby year or unrelated first result.
Old failed cache entries are retried after the matching upgrade. The per-release
year remains visible even when the catalog records an earlier festival year.

Image payloads have a 64 MiB global budget and 512-entry ceiling, with no more than
128 negative entries. Least-recently-accessed entries and expired entries are
removed on cache writes and initialization. Reads touch recency at most once per
ten minutes; image delivery fills legacy size metadata. Positive TTL remains seven
days; failed lookups retry after five minutes rather than an hour. The browser's
256-entry request cache now expires failures and tracks recency too. Posters are
still requested only for visible cards, with shared requests and small thumbnails.
MongoDB metadata/storage overhead is additional; removing cache records makes
storage reusable rather than necessarily shrinking its allocated data files.

All 44 Python tests and the JavaScript matching tests pass. The full isolated
integration/browser suite passes, including real Mongo byte-budget eviction,
negative TTL and old-failure retry, account preference restoration and failed-save
rollback, menu copying, phone/tablet layout checks, both-theme divider colors,
restart persistence and Redis recovery. Live production API checks retrieve
posters for RRR (including AKA release names), Bandar, Satluj and Ghamasaan (including
Ghamsaan spelling). Image payloads total 2,618,628 bytes across an 85-entry cache
at the validation snapshot, within the budget. See
[the live cache validation](smart-poster-cache-validation.json).

The final deployment is healthy, user/torrent/session identity digests match, the
refreshed archive passes SHA-256 verification, and disposable fixtures were removed.

## Latest image tag and empty search page

The running deployment, Compose distribution, build/migration documentation and
smoke-test defaults use `autolycus:latest`. The former `autolycus:single` local
alias was removed. The image archive exports the latest tag only. Files named
`compose.single.yml` still describe the single-container architecture.

The secondary title filter and list/poster selector now render only when results
are available, retaining the requested minimal empty page. Browser checks assert
both are absent before searching, and then verify the remembered layout after
controlled search results, reloads and a fresh browser. The complete isolated
integration/browser suite passes, including touch layouts, preference rollback,
cache policy, restart persistence and Redis recovery. Production is healthy, data
identity digests match, and the refreshed latest-tag archive passes SHA-256.

HomeSense and PortHub were reviewed read-only for LAN streaming. No changes were
made to either application's runtime or to URM2. HomeSense uses a signed/encrypted
local-first WebSocket/MSE handoff; its go2rtc WebRTC listener is disabled. Autolycus
currently uses authenticated HTTP range responses through its current origin.

## Direct bytes and client playback — 2026-10-31

`playback-validation.json` records the shipping image, observed resource samples,
limits and the complete isolated test results. One container still runs from
`autolycus:latest`. Rust serves authenticated WebRTC file ranges; Python authorizes
short session-bound leases; the React player and compatibility codecs run on the
viewer’s device. The same public PWA origin handles signaling, and HTTP ranges
remain the fallback. HomeSense, PortHub and URM2 were not changed.

The full suite passes on image `f657e085…`, including generated Dolby/DTS audio,
10-bit HEVC software fallback with nonblank-frame checks, multi-audio switching,
seeking, external and embedded English/Hindi subtitles, actual HTTP fallback,
phone widths 320–768, eight-peer limits, restart persistence and Redis recovery.
The shipping image only adds descriptive subtitle language labels/defaults after
that suite. Its production health and preserved users/torrents/session identity
were checked after rollout. The latest-tag archive was rebuilt and checksum-verified.

OpenTabs additionally verified original-byte integrity through the published LAN
UDP address, excluding the directly reachable Docker candidate. Real library
files were mounted read-only in an isolated test instance. A 1080p H.264 movie
played with Dolby audio, alternate tracks and a seek past ten minutes. A real
10-bit HEVC movie produced decoded video/audio through the optional client path
and sought past two minutes; embedded subtitle tracks and timed cues loaded.
Software HEVC is device-dependent and was not shown to sustain realtime on every
client. Native-supported video remains packet-copy playback. There is no server
playback decode/remux/transcode process or streaming disk cache.

The Rust byte process used roughly 12–14 MiB RSS in these observations. A measured
three-second seek burst used about 12% of one CPU; it is not an idle or throughput
benchmark. Client byte pages are capped at 16 MiB, demux caching at 4 MiB and the
subtitle index at 2 MiB. Server send/read buffers and peer counts remain bounded.
Physical iPhone Safari/PWA, network handoff and restrictive internet NAT require
separate device/network testing; viewport checks do not substitute for those.

## Minimal player presentation — 2026-10-31

Removed the padded modal header, duplicate title, connection footer, standalone
selects and external compatibility controls. A single overlay title and close
button sit on the video. Audio, subtitles, speed and playback options use the
existing Neutral control-bar appearance with public Video.js menu primitives.
The movie retains its intrinsic aspect ratio with contain sizing inside the
full-window stage described below.

The final exported UI passes the dedicated playback suite: one title/no wrapper
assertions, integrated audio/subtitle selection, speed, fullscreen, direct/HTTP
delivery, Dolby/DTS and optional HEVC playback, external/embedded subtitles, and
phone widths 320/375/390/414/768. Settled menu and cinematic-width phone screenshots
were visually reviewed. Production health and preserved data identity pass after
rollout; the latest-tag distribution archive was refreshed and checksum verified.

## Full-window playback, touch gestures and episode queue

The final image keeps a black, square-cornered stage at viewport size before
metadata arrives; cinematic content retains its aspect ratio inside that stage.
Light/dark themes and phone widths 320/375/390/414/768 were checked. Real Chromium
touch input verified brightness/volume swipes, double-tap seek in both directions,
hold at 2× and restoration of the previous rate, cancellation, and hold-drag seek
preview with a single seek committed on release. Opening and closing on a touch
device requests and releases browser fullscreen. Physical iPhone Safari/PWA
behavior remains unverified; unsupported fullscreen keeps the full-window stage.

Generated episode fixtures verified natural filename ordering (1, 2, 10), nested
folders, in-player selection, previous/next, automatic continuation, and disabling
autoplay-next. The episode popup was inspected at phone size and uses one scroll
region. Discovery is bounded and uses an authenticated names-only listing that
skips recursive folder sizing, torrent lookups and public-link creation.

The complete media suite passed before the final menu and lightweight-listing
refinements. Focused playback/touch/episode checks then passed on the final image.
No server decoding/transcoding process appeared during playback.

Final rollout health and HTTP UI checks pass. Before/after identity digests match
for 3 users, 32 torrent records and 119 sessions. The refreshed archive checksum
passes, and disposable playback containers and volumes were removed.


## Latest media, public-player and settings release

The active container is explicitly named `autolycus` and uses `autolycus:latest`.
The GPU override is enabled on this machine; the base image was also checked
without a GPU. Before/after deployment identity snapshots match exactly for
**3 users, 32 torrents and 119 sessions**. The existing public address and host
ports are unchanged. A transient FTP passive-port collision required retrying
startup and reattaching the existing Compose network; host and public API checks
then returned 200. PortHub and HomeSense were not modified.

The updated settings categories, profiles, server-paged 125-session search,
playback bookmarks, disabled/missing quality choices, direct Episodes list,
private/public Download buttons and menu-dismiss behavior pass browser checks.
Phone/tablet layouts were exercised at 320, 375, 390, 414 and 768 CSS pixels.
The compact storage tooltip and navbar ring use actual drive usage/total;
Autolycus's footprint is separate and no adjusted application capacity is shown.

The throttled HTTP test switches down to an existing lower quality and recovers
Original after bandwidth and buffer stabilize. Auto never starts a transcode.
Real Wall-E Hindi audio switching, Papa Yaar captions and client-side Avatar
EAC3 audio were checked using read-only source mounts. Manual alternate-audio
offset/rate and a synthetic three-second auto-alignment case pass. Public-link
playback was checked anonymously, including actual RTC bytes, embedded/sidecar
captions, opaque keys, scoped grants, revocation, refresh and download precedence.
The supplied live Hanuman Ansh link played in OpenTabs beyond one minute.

Explicit FFmpeg CPU/NVENC jobs, two-slot limits, queued/running cancellation,
quiet URL-download cancellation and nonzero download exits pass integration
checks. The real sprite task produced a bounded PNG in MongoDB and added no files
beside the movie. OpenSubtitles authorization/search/selection contracts were
verified with a mock; a real provider account must be connected in Settings.

These automated checks do not verify physical iPhone behavior or actual Cast/
AirPlay receivers. Native codec and hardware decoding support remains device
specific, and audio alignment is best-effort. Runtime samples above are workload
observations, not peak-memory caps or comparative performance benchmarks. See
`playback-validation.json` for the final image/archive and detailed coverage.

## Playback-priority preview extraction (2026-11-01)

Preview probes and individual FFmpeg frame extractions now poll foreground
playback/transcode activity every 250 ms. When activity is observed, the current
child is killed and reaped before the preview task retries after 30 seconds.
This also covers ffprobe, rather than checking only between thumbnail cells.
Both probe and frame commands retain idle I/O priority and niceness 19; FFmpeg
retains one decoding thread. This is cooperative scheduling, not a CPU or RAM
quota: a small amount of work can occur before the next activity check.

`python tests/test_preview_yield.py` verifies a live child is interrupted/reaped,
a deadline terminates a stalled child, and successful/error output is preserved.
The disposable-container `test_preview_fill.py` still produces a real 160×90 PNG
cell without generated letterboxing. The video-top network badge was removed;
connection diagnostics remain in the Playback settings menu.

The 2026-11-01 isolated browser run also passed root sign-in routing, local
search, overflow checks at 320/390/768 CSS pixels, naturally ordered episode
selection, quality-menu layout, captions, URL refresh/resume and the management
page logo returning to `/`. This does not verify physical mobile fullscreen
behavior or the still-pending online-source and torrent-preview features.

## Online sources — work in progress

The guest provider lookup is implemented with strict catalog title/year/kind
matching, explicit TV season/episode, two concurrent lookup slots, bounded JSON
responses, a 35-second provider deadline and a separate cache (64 entries, 120
seconds for sources, 30 seconds for empty results). Lookups require the existing
account session and cache misses are limited to 30/hour/account. No user-supplied
URL is fetched. Provider player domains and media hosts are allowlisted.

`test_online_source_matching.py` passes wrong-title/year/type and URL rejection
checks. `single_container_online_sources.py` passes real-session authentication,
invalid IMDb ID rejection, authoritative metadata instead of supplied title/year,
TTL and repeated-lookup reuse against a mocked provider in the disposable app.
A real WALL·E lookup found five MP4 sources. A refreshed provider-header range
request returned 206, but the equivalent request without provider headers returned
429. Browser playback/source switching is therefore **not yet implemented or
verified**; the UI remains disabled pending the bounded byte-relay integration.
The protocol reference's MIT license is included under `api/third_party`.

The subsequent relay integration passes byte-exact mocked partial/suffix/open/full
range tests, invalid-range rejection, account ownership, required provider-header
forwarding, absence of forwarded user credentials, stream-slot release and the
foreground-playback marker. It uses opaque account-bound grants (two-hour rolling
TTL; at most 256 grants), 64 KiB upstream chunks and at most eight upstream streams
per API process. Provider URLs are renewed on subsequent requests after 90 seconds
and the replacement must preserve both source identity and byte size. Redirects
are not followed. No decoding, transcoding, whole-file buffering or media disk
cache is used. These are code limits, not measured total-process memory caps.

`single_container_online_real_range.py` also passes the real authenticated WALL·E
lookup → opaque source → info → 32 KiB relay HTTP 206 flow with a valid MP4 ftyp
box. This proves byte transport, not full browser playback. The shared transport
and quality hooks now recognize online-source info endpoints; player UI/source
switching and full playback tests remain pending and the feature is not yet live.

The Cinema UI integration now passes a real browser run for Watch now, decoded
video, Source menu switching, preserved timeline/autoplay, refresh URL resume and
390px overflow checks. The existing Cinema regression also passes sign-in/root
routing, local search, 320/390/768px layouts, episode switching, quality/captions,
local URL resume and the management logo link. Native fallback no longer shows a
misleading failure banner over an already playing video. Full physical iPhone,
Cast/AirPlay and every provider title/codec are not covered by these runs.

The final online browser check additionally waits for the video clock to advance
following switching and refresh, confirms the startup loader clears, and verifies
browser Back dismisses the online player without leaving the loading overlay.
The reviewed phone screenshot shows an actual decoded frame, without a fallback
error banner. The relay test also cancels an active response iterator within an
already-cancelled scope and confirms both client closure and restoration of all
eight stream slots; cleanup is shielded and time bounded.

## Torrent contents — work in progress

`tests/native_torrent_preview.py` passes against libtorrent 2.0.7 in the disposable
container: a real local seed supplies metadata for three files (two videos),
while the preview handle downloads zero payload bytes and retains zero file
priorities. The test also verifies same-account reuse, cross-account denial and
explicit removal. The implementation uses upload_mode while fetching metadata;
this installed binding does not expose default_dont_download. File priorities
are initialized to zero before adding the magnet.

The lazy preview engine reuses LibTorrentSession, with four global leases,
two/account, 80 peer connections, one disk-I/O thread, one hashing thread, 4 MiB
metadata cap, 4,000 files, 60-second metadata polling deadline and 15-minute idle
expiry. Unsafe paths and symlink entries are rejected. Temporary state is under
`/downloads/.previews`, excluded by hidden-directory catalog scanning. Its future
payload path has an 8 MiB/s aggregate download cap, 256 KiB/s upload cap and a
conservative 2 GiB aggregate traffic budget with a safety reserve. No UI or
payload streaming path uses this engine yet. The contents endpoints and manager
are implemented in the worktree, not deployed; selective download, preview
playback, integration tests and search UI remain unfinished.

## Selective download backend — work in progress

`native_torrent_selection.py` passes real local-swarm transfer with exact SHA-256
for the chosen file, the unselected file absent, and progress totals counting
only the selection. Native stop/start and a fresh LibTorrentSession both retain
the same priorities. Priorities are supplied with known metadata before adding
the torrent, rather than filtering after payload download starts.

`single_container_torrent_selection.py` passes authenticated metadata lookup,
strict file-index validation (including rejecting booleans/fractions), selected
file transfer, Mongo persistence of selected indices and bounded metadata,
duplicate prevention and API resume preserving file priorities. It also confirms
metadata blobs are excluded from torrent-list JSON. Its native-engine transfer
is real; poster/index/socket callbacks are isolated in that API contract test.
The separate normal native torrent + SOCKS tracker fallback regression still
passes with the modified engine wrapper.

Selective downloads skip the existing cross-account directory-copy shortcut,
which could otherwise bring in unselected files. This initial path supports v1
and hybrid torrents; the existing normal wrapper requires a v1 hash. Native
metadata browsing can still list v2-only content, but does not claim download
support for it. The new selection backend is not deployed yet: search dialog
integration and bounded playable previews are still pending.

## Torrent streaming and search dialog integration

`native_torrent_ranges.py` passes verified byte-exact cross-piece reads, near-end
seeking and file changes against a real local seed. It checks zero payload while
browsing metadata for five seconds, bounded partial transfer rather than the whole
torrent, cancellation, suspended piece priorities and deletion of allocated
preview data after close. `single_container_torrent_selection.py` also passes
real HTTP partial/suffix ranges, invalid-range rejection and stream-slot release.

The initial browser preview flow passes file discovery/filtering, natural episode
ordering, 320/390/768px layout checks, real video in the shared player, returning
to the file list and queueing selected download. Its search response is a fixture;
metadata and video bytes come from a real local libtorrent seed. The disposable
API uses `tests/torrent_preview_peer_fixture.py` to connect that local seed
explicitly, instead of depending on public DHT/LSD discovery. This hook is never
part of the production image. Normal tracker discovery/fallback is covered by the
separate native swarm regression.

Browser testing found and fixed an unstable resolver callback that restarted
leases on viewport changes. File dialogs shrink for short filtered lists; the
normal list virtualizer now supplies the required row index. The service worker
accepts account-bound online and torrent-preview media routes. The preview engine
retains metadata peer connections to avoid upload-only disconnects while browsing;
see the upstream behavior in
https://github.com/arvidn/libtorrent/blob/v2.0.7/src/bt_peer_connection.cpp.
No file payload is requested until preview playback or an explicit download.

The final browser run also verifies that the selected download **completes**, its
total equals the chosen file only, its database metadata is absent from list JSON,
and the poster menu opens the same contents dialog. Preview peers are paused and
disconnected before permanent-download startup; this avoids seeds rejecting the
second connection from the same machine. All these changes are now deployed in
the single `autolycus:latest` container; the public health check returned 200.
The distribution archive still needs refreshing after the remaining goal audit.

## Real Avatar LAN/startup audit — 2026-11-01

The 38,579,201,629-byte Avatar file was mounted read-only into a disposable app,
under its test account. Its 15,443,048-byte moov index is at byte 38,563,758,581,
so startup must fetch the end of the file before parsing tracks.

A browser using the public HTTPS origin (mapped only inside that browser to the
isolated app) connected to the advertised home-LAN UDP candidate. The test
filtered out the container candidate so it could not accidentally take the
container shortcut. It fetched the complete index in 60 bounded requests, with
an exact SHA-256 match: 155 ms connection setup and 1,459 ms index transfer.
These are warm local observations, not WAN throughput guarantees.

The actual root-page custom player separately parsed both EAC3 audio tracks in
1.26 seconds. Headless desktop Chrome reported no native HEVC support. Explicit
client compatibility playback produced 29 decoded frames at 3840×2076 and
decoded audio; first frames appeared about 4.05 seconds after selecting it. That
proves the short client fallback path, not sustained full-movie performance.
No FFmpeg, HandBrakeCLI or ffprobe process was present in a server-process sample.
Physical iPhone/native hardware decoding and HDR fidelity are not verified here.

Player info now marks foreground playback immediately for private, public,
online and torrent modes; successful RTC offers also mark it. The priority
contract test verifies each mode and confirms a thumbnail task retries before
calling its generator. This closes the window before the first 20-second lease
renewal. Mid-frame cooperative interruption remains covered by the preview-yield
test. See `avatar-lan-validation.json` for the measured results and test context.

The startup-priority change is deployed as image
`sha256:0ad8a93ec90a6ce72524543772d2c47a8276d189bedc3263b72cc6e61208be77`
under `autolycus:latest`, container `autolycus`; public health returned 200.
The read-only Avatar audit container was stopped after collecting results.
