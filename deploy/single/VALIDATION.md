# Production validation — updated 2026-10-31

The migrated deployment runs one healthy container,
`autolycus-single-autolycus-1`, from `autolycus:single`.

| Measurement | Result |
| --- | --- |
| Final image ID | `sha256:ec0656f0b2c266b6fad746d135904659ad6ff63f5ae8e3756e7dc45a582e1c6c` |
| Image compressed content size reported by Docker inspect | 755,362,753 bytes |
| Existing eleven images, summed compressed content size | 1,863,404,306 bytes |
| Reduction in summed compressed image content | Approximately 59.5% |
| Docker CLI reported image size | 2.65 GB; original images summed to approximately 7.44 GB |
| Exported Docker archive | 751,113,665 bytes, approximately 716 MiB |
| Observed production idle memory | Approximately 490 MiB |
| Observed production idle CPU sample | 0.59% of one CPU |

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

Storage now reports deduplicated Autolycus usage over capacity after subtracting
space occupied outside Autolycus, shared by all users over HTTP and Socket.IO.
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
