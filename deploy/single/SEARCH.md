# Search behavior

Search requests still use the configured Jackett Tor proxy. No proxy, indexer,
FlareSolverr, or torrent peer settings were changed for this feature.

- The second title filter stays visible when results exist and automatically
  receives the original query on every new search. Its automatic mode uses strict
  word matching to exclude unrelated titles. Editing it enables word prefixes as
  well as bounded typos: `m` → `mu` → `mus` keeps Musafir visible immediately.
  Starting a new search restores automatic mode. Manual mode is saved with the
  existing in-app search state; users can edit or clear the filter.
- Fuse.js searches each query word independently, avoiding phrase-distance losses
  in long or multilingual release names. The secondary gate requires every word.
  Short words match complete words; longer alphabetic words permit one typo or
  adjacent transposition. Numeric terms are exact. Seasons accept their episodes,
  and software versions require the same ordered number sequence (dots or spaces).
  Accents, release separators, dual-audio/quality tags are normalized. Tracker
  names do not match the title filter. Normalized title words use a WeakMap cache.
- Matching results retain the selected sort. The default is seeders descending;
  query relevance breaks equal-seeder ties. Indexer seed counts are estimates.
- Results with zero or unreported seeders remain available below seeded results.
- Searches wait for indexers to finish, fail, or reach their own timeout. There is
  no slower-source checkbox or application read deadline. Users can cancel or
  start another search. Heartbeats keep the stream alive while sources are busy.

## Copying magnets

Copy and Download first use an existing valid magnet or info hash (hexadecimal
or base32). Otherwise, a server-issued, user-bound reference identifies the
result's local Jackett download endpoint. On click the API requests metadata
through Jackett, accepts a magnet response or converts a `.torrent` file with
libtorrent, and returns a magnet. The UI copies it with the existing clipboard
and manual-copy fallback, or adds it to the download queue for Download.

Resolution reads at most 4 MiB, permits four concurrent requests, times out at
65 seconds, and caches successful resolution for an hour. Reference expiry asks
the user to search again. Internal Jackett download links are removed from
returned results so their credentials are not exposed as source links.
External redirects are refused; Jackett must supply metadata or a magnet.
No torrent contents are downloaded by Copy magnet. If a source fails to provide
usable metadata, the UI offers an actionable error and the source-page link.

Validation includes generated `.torrent` conversion, magnet redirects, retained
signed download parameters, size and redirect bounds, user ownership and token
expiry, zero/unknown seeder coverage, deep-search retry limits, and browser checks
for automatic title filtering, seed ordering, and the Copy magnet clipboard flow.

## Live tuning samples

[The tuning report](search-validation.json) records 16 live queries and 17,886 raw
results spanning language, genre words, old/new titles, years, series, seasons,
and software/version names. These are bounded probes, not a complete indexer
availability audit. Filtering retained matching words in long filenames that the
previous phrase search missed, and excluded unrelated near-spelling matches.
Measured warm local filtering medians were approximately 1.5–14 ms for these
277–2,879-result samples. No AI model or runtime dependency was added.

`node tests/search_matching.mjs` exercises 52 curated matching cases, 20 substring
negatives, the full Fuse pipeline, and seed-order preservation. Run after installing
the UI dependencies. Mood/genre searches remain dependent on what indexer titles
and metadata contain; these checks cannot guarantee all content is available.

## Faster first results

Searches use recent response-time and success history to schedule faster, reliable
sources before slower ones, keeping all configured sources and the existing
20-request concurrency limit. Timing excludes time waiting for a concurrency slot;
cancelled work does not count as a source failure. Unknown sources remain eligible
and every search still queues all sources. Timing history is stored in Redis.
Configured-indexer discovery is reused for 30 seconds.

Repeat searches stream complete, recent source batches from Redis before their
live refresh. Entries expire per source after 10 minutes, including sources that
fail to refresh. Query keys include the normalized query, indexer set, Jackett
address and deep-search mode. Cache writes are atomically limited to 16 snapshots
of at most 1 MiB each; oversized source batches can be omitted from the cache
without affecting the live search. Cached raw references stay server-side and
receive new user-bound resolution tokens before delivery.

Fresh rows replace cached identities without duplicates; successful source
completion removes disappeared cached rows, including when a source is now empty.
A failed source retains its still-recent rows. Cached results refresh silently without a status banner. Users can cancel or start another
search, and cancelled workers are cleaned up. Redis/cache failures fall back to
normal live searching. A first-ever query still depends on source response times.

The isolated real-Redis fixture measured 405.20 ms to the first result with an
unfavorable source order, 28.06 ms with learned prioritization, and 0.37 ms from
cache. These controlled API measurements verify the mechanism, not production
speed or browser paint time. The UI batches incoming rows for up to 100 ms.

## Account-synced list and poster views

Search opens in its existing list layout unless the account has saved thumbnail
view. The list/grid buttons match the home-page control and save independently as
`preferences.search_view_mode` through the existing account preferences endpoint.
Reloads and a fresh signed-in browser restore that choice. Saving is optimistic;
failed saves restore the previous view and show an error rather than pretending
the preference was stored. Home view and FTP preferences remain independent.

Poster view keeps the same filtered, seed-sorted release results. Cards show the
movie/series title, year, quality/season/episode, seeders, size and source.
Copy magnet, Download, source/Tor links and IMDb use the same action menu as Home. Copy and Download use the
existing magnet and `.torrent`-conversion paths. Missing posters use a stable title
placeholder; known software/book/music categories do not request movie posters.

Rows are virtualized and only visible/near-visible cards request metadata. Client
requests deduplicate films across release quality and indexers, with three network
requests at a time and a bounded queue/cache. Poster providers reuse the home
library's TMDB/IMDb lookup path; IMDb images use 360-pixel thumbnails rather than
full-size originals. The server also deduplicates work, permits three lookups at a
time, caps pending keys at 64, accepts at most 1 MiB per image, and retains up to
512 entries and a global 64 MiB image-data budget, evicting the least recently
accessed entries. At most 128 negative entries are retained. Matched entries expire
after seven days; unmatched entries retry after five minutes. Images are served through authenticated same-origin endpoints.
Title/year checks avoid attaching a plainly unrelated film or wrong-year remake.
No new runtime dependencies or model weights were added.

Both layouts were checked in touch-emulated Chromium viewports at 320×568,
375×667, 390×844, 414×896 and 768×1024, plus desktop. Checks cover horizontal
containment, phone touch targets and menu actions, last-row access above mobile bottom
navigation, real image delivery, per-release lookup deduplication, copy magnet,
no poster lookups in list view, silent refreshing, independent server preferences,
fresh-browser restoration, and failed-save rollback. This is viewport/touch
emulation, not a test on a physical iPhone or Safari.

### Home-style visual refinement

The Search view switch sits beside the secondary title filter, separated by a
thin vertical divider. Its neutral icon styling matches the minimal filter bar.
Each button is square and matches the filter height: 28 pixels on desktop and
44 pixels on phones. The control remains available before and after searching.
The main search field keeps its full width; Home's switch is unchanged.
Search thumbnails use Home's poster-only proportions,
neutral fallback, rounded corners, bottom title/metadata gradient, compact
12-pixel title and 11-pixel details, grid columns/gaps, and shared FileMenu actions.
The separate card body, rating badge and large colored download panel were removed.
The menu is visible without hover; its phone target and action items are at least
44 pixels, with the original compact Home target size on desktop. Account sync,
lazy/deduplicated images, filtering, sorting and list view remain in place.

The isolated browser checks cover menu-based copying/downloading access,
secondary-field/button alignment at each tested viewport, no horizontal overflow, both
view preferences, fresh-browser restoration, failed-save rollback and last-row
menu access above mobile navigation.

### Intelligent cache and renamed films

Only visible-card posters are looked up, with quality variants deduplicated. The
server enforces both a 64 MiB image payload budget and the entry ceiling. MongoDB
metadata and allocated database storage have additional overhead; eviction frees
pages for reuse. Reads update recency with ten-minute write throttling. The client
also has bounded, expiring metadata requests, so failed requests are not retained
for the lifetime of an open app.

Release AKA text and bilingual/acronym formatting are normalized before lookup.
When the catalog's displayed name or primary year differs, the fallback checks its
original/alternate titles and explicit release dates before accepting the image.
This handles renamed films and differing festival/theatrical dates without a
blanket year tolerance. Failed entries from the older lookup are retried after the
upgrade. The card retains the release filename's year when available.
