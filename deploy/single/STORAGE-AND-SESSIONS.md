# Storage relocation and persistent sign-in

The installed repository and its complete `volumes/` tree now live at
`/mnt/WD8TB/autolycus`, moved from `/mnt/WD512/autolycus`. The 8 TB ext4 filesystem is
mounted at `/mnt/WD8TB` (UUID `cee81b24-57da-417f-9be0-fd50d8ff8a0f`). After the
verified cutover, the old repository path remains a compatibility symlink. Docker's
shared image/build cache remains in its existing system-managed location; all
application bind-mounted data and the distributable archive live on the HDD.

The relocation uses a live initial copy, a stopped final sync, content checksums
for mutable service state, a full metadata reconciliation, and head/tail samples
from large payloads. User, torrent and session identity digests are compared
before the verified SSD copy is removed. Repository history, uncommitted files,
ignored files, credentials, old rollback data, downloads, hard links, ownership,
ACLs, extended attributes and sparse files are included.

## Drive capacity

Previously, three separate implementations scanned each user's files and
reported a per-user virtual capacity. They counted hard-linked copies more than
once, which could show values such as 607/753 GB on a physically smaller SSD.

All storage responses now come from `shared.modules.storage_usage`. The selected
display is **Autolycus occupied / (drive capacity − occupied outside Autolycus)**.
The occupied value includes the repository, service data and downloads on the
downloads drive. Allocated blocks are deduplicated by device/inode, so hard links
and overlapping mounts count once. The repository is mounted read-only at
`/installation` for this measurement. New accounts see the same figures as
existing accounts. A background sample runs every 60 seconds; HTTP, Socket.IO and
job updates use the shared snapshot instead of scanning files per request. The
UI refreshes every 30 seconds.

## HomeSense comparison and chosen policy

The running HomeSense installation was inspected without changing it. Its
configuration uses `session_days=30`. Its auth routes issue HttpOnly,
SameSite=Lax persistent cookies, backed by durable server-side sessions; session
validation renews the server lifetime while in use.

The user explicitly chose the same **30-day rolling duration** for Autolycus.
Every authenticated HTTP access renews the cookie and Redis TTL. MongoDB expiry
is checkpointed hourly, with a matching recovery allowance, to avoid a database
write on every polling request. Redis cache loss can recover an active session
from MongoDB; revoked or expired records cannot recover. No password or session
token is stored in frontend localStorage.

The old session-only cookies had no Max-Age or Expires. Sign-in also raced an
unawaited sign-out, and network errors could incorrectly send the UI to login.
Those paths are corrected. Auth responses are marked no-store and all API
requests bypass service-worker caching. An installed app can close and reopen
with its persistent cookie, while a temporary network failure leaves its login
intact. Explicit logout, device revocation, browser-data deletion or more than
30 days without access requires another sign-in.

If an old Safari home-screen installation has already discarded its former
session-only cookie, sign in once inside that installed app after deployment.
The new cookie can then persist normally. Automated browser tests cover browser
process close/reopen and simulated auth-network failure; they do not constitute
a test on a physical iPhone.

## Verification

Eleven unit tests cover shared application usage, hard-link deduplication,
concurrent snapshot refresh, persistent cookie attributes,
cache recovery, expiry/revocation, hourly checkpoints, rolling renewal and
returning just before the inactivity limit. The isolated full-stack test covers
fresh-account storage over HTTP and Socket.IO, durable-session recovery, cookie
renewal, credential verification, logout, browser close/reopen and transient
network failures, alongside the existing application workflows. The installation
also refuses to initialize a blank database if its required existing data mount
is absent.

The completed relocation's exact mount paths and identity checks are recorded in
`relocation-validation.json` (local-only, excluded from Git) beside this document.
