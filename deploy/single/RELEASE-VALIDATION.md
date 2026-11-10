# Release validation — 2026-11-01

This is the current completion audit. Earlier sections of `VALIDATION.md` record
intermediate states and are superseded where they say a shipped feature is pending.
The exact image, archive hash, sizes, identity counts and limitations are recorded
in [playback-validation.json](playback-validation.json). Captured test output is in
[validation-results-2026-11-01.txt](validation-results-2026-11-01.txt).

## Requirement audit

| Requirement | Implementation and direct evidence | Result |
| --- | --- | --- |
| SSD application/state, HDD media | Running container mounts `/installation` from `/mnt/WD512/autolycus`, `/data` from its `volumes/single`, and `/downloads` from `/mnt/WD8TB/autolycus/volumes/downloads`. User/torrent/session IDs were compared immediately before and after deployment. | Passed |
| Single distributable production container | Running name `autolycus`, tag `autolycus:latest`, image `sha256:aed2551e664b992a7ab89467de3d5eff193b4f9ed98c0d9d352a5f2862c59bf3`; health healthy, local and public `/api/ping` HTTP 200. GPU remains an optional Compose override. | Passed |
| Stable root load, authentication and navigation | `single_container_cinema_browser.py`: anonymous root redirects to sign-in, login returns to `/`, title is Autolycus, management logo returns to root. `single_container_cinema_visual_audit.py`: hero height changes less than one pixel through loading at 1440/390/320px. | Passed |
| Artwork visibility and ownership | Source-keyed image load state fixes a cached-image race. Visual audit checks actual image loaded state/opacity, no ownership badge on artwork, and library marks below artwork. No expanded management navbar, Cinema nav button or right details pane. | Passed |
| Rich discovery and title pages | Real catalog details supply ratings, synopsis, cast, runtime, genres, artwork and trailers; full details are fetched after title-only library matching. Visual audit checks synopsis, minimal trailer iframe, and recommendations seeded by a completed watched title. Browser catalog tests cover search, shelves and direct owned playback. | Passed |
| Search and download handoff | Cinema detail/search links carry the exact title/year into management search. Existing title filter, list/poster preference and indexer controls remain available after searching. Search contents dialog is exercised from both result-list and poster-menu entry points. | Passed |
| Settings/profile consistency | All seven settings sections, aligned search/filter and themed profile menu checked in dark/light at 1440/390/320px. Switching profile persists after refresh; Manage profiles opens the correct section. | Passed |
| Minimal video/trailer popups | Trailer iframe has no extra header/footer bars. Player browser regression checks controls, episode menu, subtitles, quality list, URL resume and no top network badge. Network diagnostics remain inside Playback settings only. | Passed |
| Compatible online playback in the custom player | Separate real-provider browser runs resolved MovieBox MP4 streams, decoded video, switched sources and checked phone layout/Back navigation. Relay contract verifies exact partial/suffix/full ranges, account-bound opaque grants, no account credentials forwarded and cancellation cleanup. | Passed with provider limits below |
| Source continuity and failure recovery | Controlled byte-adapter browser test switches library → online → library while playing at 1.25× and paused at 1.5×, retains timeline, and verifies the library server bookmark. An unavailable source returns recoverable HTTP 502; returning to the library retains position/state. | Passed |
| Torrent contents and selected downloads | `single_container_torrent_selection.py` and real local-swarm browser test: natural file ordering/filtering, list/poster entry, selected download completes, totals include only chosen files, metadata is excluded from list JSON. Existing libtorrent engine is reused. | Passed |
| Resource-bounded torrent previews | Native range tests verify zero payload during metadata browsing, exact cross-piece/seek/file-switch bytes, cancellation, suspension and data deletion. Browser test plays real seeded video at phone widths and returns to the file list. Four global/two account leases, bounded transfer/concurrency and hidden temporary sparse storage; see README for exact budgets. | Passed |
| FMHY/Jackett audit including Torlock | `indexer-audit.json`: FileMood and TorrentsCSV verified with seeded magnet results for several movie/software queries and enabled; DaMagNet not enabled because direct magnets were absent. Torlock is absent from installed definitions and removed upstream; no speculative scraper added. Production retained 48 source configurations through Tor. | Passed |
| Large Avatar LAN-first startup | `avatar-lan-validation.json`: real read-only 38.6 GB file, public HTTPS origin, forced advertised LAN candidate, SHA-exact 15.4 MB end index in 1.459 seconds. Actual player finds both EAC3 tracks; explicit client fallback decodes 3840×2076 video and audio. | Passed within measured scope |
| No automatic server video encoding; foreground priority | Media routes relay/read original bytes. Playback-priority contract checks private/public/online/torrent modes before frames or lease renewal. Preview-yield tests interrupt/reap ongoing probe/frame processes. No ffmpeg/ffprobe/HandBrake process in sampled serving process list. Explicit user-requested transcoding remains separate. | Passed |
| Desktop and phone flows | Browser flows cover root/auth, discovery/details, management/settings/profiles, source switching, local player/episodes/resume and torrent preview/download. Viewports include 320/390/768px and desktop; actual physical-device limitations are explicit below. | Passed in browser viewport scope |
| Offline archive and installation | Archive exported from the deployed image, SHA-256 checked, then actually imported with `docker load`. The mobile follow-up image boots with fresh data and 2 CPUs/2 GiB and no GPU, serves local JPEG, configures two starter sources/Tor and permits signup/sign-in. Restart preserves the session and intentional proxy/indexer changes. Offline Compose uses `pull_policy: never`, exact name/tag and no build/GPU requirement. | Passed |

## Distribution

- Archive: `dist/autolycus-single-linux-amd64.tar.gz`, 756,327,432 bytes.
- SHA-256: `7357c926eecd4271eb4699e83dece7e86f45146f28146fede6f55881dcab80d1`.
- Docker's reported image content size: 760,599,147 bytes; this is not a claim
  about an unpacked root filesystem's disk allocation.
- Production after deployment: 3 users, 32 torrents, 43 current session records;
  all IDs present immediately before deployment remained present afterwards.
- Single idle observation: 487.6 MiB RAM and 0.74% of one CPU core. This is not
  a peak benchmark or a container quota.

The archive contains the image, not existing databases, accounts, credentials or
downloaded media. `.dockerignore` excludes local data and test fixtures. Unique
service credentials are generated on first boot. Fresh source defaults apply
only to a new Jackett configuration; upgrades preserve existing choices.

## Mobile follow-up

The mobile player opens with a landscape control surface. Play requests native
fullscreen synchronously where available, followed by landscape orientation lock;
a HomeSense-style CSS rotation preserves the custom player when those APIs are
unavailable. Fullscreen remains available as a button, with a separate Fit/Fill
button for letterboxing versus cropped fill. Rotated seeking and touch gestures
map physical coordinates back to player coordinates. Native top-layer menus are
explicitly rotated and positioned; they otherwise ignore ancestor transforms.

Touch controls fade after 2.5 seconds of playing inactivity. Single taps show or
hide controls, including while paused, without changing playback. Play/pause stays
on its button; double-tap seeking and hold-to-2x remain. Settings and sustained
control interactions keep controls visible. Desktop keeps its existing activity
and keyboard behavior.

Mobile management navigation has no extra logo item. Its root/Cinema shortcut is
beside metadata search. Settings categories stay in one horizontally scrollable
row. File collections and metadata search load subsequent pages automatically;
existing cards remain visible on page failure, with Retry. Folder lists use the
same virtual view. Only nearby cards, live socket subscriptions and watch-progress
requests are active; loaded lightweight records are retained for list navigation.
The existing TanStack virtualizer is reused, with no new library or video work.

`single_container_mobile_navigation.py` verifies 260 real indexed/database
collections, list/grid/search scrolling, bounded mounted-card counts, failed-page
retry, 320/390px layout, API-disabled landscape fallback, touch control visibility,
Fit/Fill, seeking, double-tap, 2x hold and rotated menu bounds. The native fullscreen
script separately exercises actual Chromium fullscreen with a landscape API spy.
The desktop script verifies unchanged desktop navigation/settings/player behavior
and virtualized folder rows. These use generated media and a marked disposable
fixture installation, never production accounts or videos.

Safari's arbitrary-element fullscreen and orientation-lock limitations still
apply: the fallback fills the available viewport and retains the custom controls,
but cannot force Safari to hide its browser chrome. See the
[WebKit fullscreen issue](https://bugs.webkit.org/show_bug.cgi?id=328773) and
[orientation-lock issue](https://bugs.webkit.org/show_bug.cgi?id=257695).

## Practical limits

Online playback currently supports compatible MovieBox MP4 sources, not every
external streaming site. Signed iframe-only sites were not substituted for the
custom player. A provider CDN timed out during testing; failures are recoverable,
but Autolycus cannot guarantee external source availability. Controlled adapters
test failure/state handling separately from the successful real-provider runs.

Torrent preview tests use a real local seed with a disposable-only explicit peer
connection. Normal tracker discovery has a separate native regression. Public
swarm availability is external. Preview payload uses temporary disk and bounded
RAM/CPU/network resources; it is not zero-resource streaming. The existing
permanent downloader supports v1/hybrid torrents, not v2-only downloads.

LAN evidence proves the original large file's bytes can bypass the public proxy
from the same public browser origin. It does not guarantee WAN peer connectivity.
Native HEVC/HDR support depends on the device; the optional software fallback
uses the viewing device's resources and can affect battery/color accuracy. The
short 4K test is not a sustained full-film benchmark. Phone viewport tests do not
replace physical iPhone gesture/orientation, Cast/AirPlay receiver or HDR checks.
Live OpenSubtitles requires a configured provider account/API key.

Temporary verification containers are removed after collecting their results.
Production accounts, media, the rollback HDD copy and unrelated applications are
preserved.

## Icon follow-up

Fit/Fill now uses magnifying-glass plus/minus icons and a tooltip, leaving one
fullscreen-corners button. The production build and deployed bundle verify the
new label and one fullscreen control. The archive was refreshed and imported;
its image ID matches the running container. Gesture, desktop and fresh-install
tests above were performed on predecessor `sha256:7ecfd9acbbf2fa674d669200e171c4dc8e2d91db529ebfee708487d7b81d9e77`; they were not repeated for
this icon-only patch.

## Registration and login-layout follow-up

Wallpaper copy is top aligned into the dark image area. Sign-in and sign-up
visual fields are capped at 400px (448px outer form with 24px padding), matching
PortHub's AuthShell. DataHub and original Autolycus shared the wider half-panel
form. Browser checks passed at 1440/1366/1024px and 390/320px without overflow.

`SIGNUP_DISABLED=true` is configured for this installation. The public uncached
auth settings endpoint reports the policy; the signup link is hidden and direct
registration pages show a closed notice. API signup rejects requests with 403
before database or session creation, including a forged client enable flag.
Existing sign-in remains available. Enabled mode creates a regular account and
session; both modes were tested in isolated CPU-only data, with the disabled-mode
and layout checks on the final shipping image. Local and public production
requests independently confirmed closed registration and HTTP 403. Invalid flag
values fail validation. Defaults stay open for independent new installations.

See `single_container_signup_policy.py`, captured results and README for the
environment setting. This is an environment gate; no database override or
first-account exception can reopen registration while it is disabled.

## Revised wallpaper placement

The maintainer subsequently chose vertically centered wallpaper copy. This CSS-only
change supersedes the top alignment described in the preceding auth checkpoint.
The production build and live exported stylesheet confirm centered alignment; the
400px form width and registration policy are unchanged. The archive was refreshed
and imported with its image ID matching the running container.

Wallpaper placement update: text is raised above center into the dark area,
with the complete group above the seats. Final live screenshots reviewed at
1440x900 and 1366x768. This supersedes the centered placement checkpoint.
