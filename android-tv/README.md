# Autolycus TV

Native Java Android TV OTT client (`dev.quiet.autolycus`, Android 14+), with the
Autolycus cinema homepage and a Media3 player. The application renders native
Android views and plays original media through a native `SurfaceView`; it does
not render the website in a WebView. Library administration stays on the server's
existing website.

The source repository and Git base commit used for the integration are recorded
in [`upstream.json`](upstream.json). The inspected server checkout contained local
modifications. No server source modifications are required by this client.

## Browse and control

The native homepage includes the original dark hero/backdrop treatment, title
artwork with readable fallback, For you / Movies / Series / My library, Continue
watching, library and discovery shelves, search and profiles. Artwork loads through
a bounded cache and workers. D-pad navigation follows movie rows; headings and
secondary per-poster icons do not interrupt movement. Focus uses subtle scale and
backplates. Details include a scrollable synopsis and episode selection.

The slim header uses a translucent gradient and subtle edge highlight, darkening
when the page scrolls to keep navigation readable. It uses no backdrop snapshots
or blur, so there is no delayed background effect. Search shows a native loading
indicator over the current page; Back cancels pending search presentation.
Local library content renders before optional external discovery is fetched;
discovery updates preserve the focused title and shelf.

Search and login use the system TV keyboard in native input surfaces. Back closes
dialogs before leaving the current screen. The Menu key on a movie opens details;
on other homepage controls it opens the server setting. Movie/trailer detail cards
also dismiss with Back, without a separate close icon.

Hold OK on Autolycus's icon in Quiet TV and select **Configure server URL** to
open Autolycus's own address setting. The address is saved privately by this app;
there is no compiled-in workstation address. Other launchers choose which app
actions their menus expose.

## Playback

Media3 1.8.0 is pinned to retain this repository's SDK 35 / Java 17 toolchain.
Original HTTP media bytes are decoded by the TV; the UI's 1080p firmware limit
does not intentionally cap video formats. Available codec, HDR/Dolby Vision
profiles and audio output support still depend on the actual TV and source.
Use Playback information for the selected format and decoder. Do not infer
Dolby Vision or Atmos output from a filename alone.

Native controls include play/pause, seeking, preview sprites where available,
audio tracks, embedded/sidecar/OpenSubtitles selection, quality versions with
Original as default, speed, fit/fill, episodes and autoplay-next, profile-aware
resume/progress, online sources and alternate soundtrack selection with sync
controls. Automatic soundtrack matching uses bounded audio windows; it does not
convert the video. Features require the corresponding server endpoint and media
tracks. Real-device validation notes distinguish implemented features from tested
combinations. Browser casting/AirPlay controls are not shown as native TV features.

Up from a playback control enters the timeline; Down returns to that same control.
Holding Left/Right increases seek steps from 10 to 30 seconds after 1.5 seconds,
then to 60 seconds after 3 seconds. Back from a player submenu returns to its
parent menu. Player and player-menu close buttons are omitted in favor of Back.
Mute applies only to this app and is retained when opening an alternate soundtrack.
On the tested Bluetooth route, mute/unmute changed the track gain in approximately
0.1 seconds. The TV reported roughly 0.5 seconds of audio-path latency; this is
not a measurement of when sound actually stopped at the speaker.

## Real-device validation

Tested on one TCL Smart TV Pro running Android 14. Its firmware caps the Android
UI at 1920×1080. For a Dolby Vision profile 8 HEVC sample, the selected decoder
was `c2.mtk.dvhe.st.decoder`; SurfaceFlinger reported a 3840×1604 video buffer
composed by `DEVICE` across the panel's physical 3840-pixel width. This confirms
that the 1080p UI limit did not reduce that sample's video buffer to 1080p.

The initial Bluetooth route stalled or remained silent despite about ten seconds
of buffered media. The Bluetooth-only PCM sink correction retained Android's
selected output route (A2DP, device type 8) and used 48 kHz stereo 16-bit PCM
(`encoding=2`); it does not force a preferred output device. The owner confirmed
both audio and video after that correction. After roughly three minutes, a
controlled interval advanced 4.026 seconds of media over 4.039 seconds of wall
time, at approximately 24 rendered frames per second, with no rebuffers and one
startup frame drop recorded. Pause, resume and seeking passed. First-frame
startup for this sample was approximately nine seconds.

The final build also passed selected-device D-pad row/column return checks,
movie-description scrolling, profile-dialog Back and search with the compact TV
keyboard. Sign-in survived process closure and signed updates. An AVC 1080p
episode played without recorded rebuffers or dropped frames; switching episodes
started the next selected file in approximately one second. Embedded English
captions rendered, and the selection survived a player reopening.

Audio capabilities are chosen when opening the player. Switching an existing
encoded speaker/HDMI session to Bluetooth may require reopening the player;
the client never forces a different Android output device.

These results cover that source and Bluetooth route only. Other Dolby Vision
profiles, Atmos output and non-Bluetooth encoded-audio passthrough remain
unverified. Subtitle variants, alternate soundtrack matching, quality switching,
online-source combinations and other advanced controls are implemented but have
not all been validated on real media and output-device combinations. Decoder or
source labels alone are not proof of a particular HDR or audio output mode.

## Sessions and network

Native session cookies are encrypted with Android Keystore and retained across
reopening and signed updates. An existing login from the early wrapper migrates
once from this application's own cookie store. Passwords are not saved. Temporary
network failures do not discard authentication. Server expiry/revocation remains
authoritative; the inspected server uses a rolling 30-day session, so indefinite
login after unlimited inactivity is not promised by the client.

API and playback authentication headers are restricted to the configured origin;
redirects are checked. External artwork receives no first-party cookie. HTTP is
supported for owner-operated LAN servers; HTTPS retains certificate validation.
Catalogue reads are on demand, not a continuous polling loop. Progress is saved
while playing and on relevant playback actions.
Native playback also publishes Android TV Watch Next progress at those bounded
save points. A launcher can show the title and resume it through an explicit
Autolycus intent. The provider receives an opaque resume ID, position/duration,
and unsigned artwork from known public image CDNs; server addresses, file paths,
profile names and authentication remain in private app storage. Completed or
removed titles and inactive profiles are pruned on catalogue refresh. Publication
depends on the firmware's TV provider and launcher support; it never changes login
state when the provider is unavailable.

## Build and install

From this `android-tv/` directory, with Java 17 and Android SDK 35 configured:

```sh
./gradlew :app:assembleDebug :app:lintDebug
bash tools/test-local.sh
adb -s YOUR_ADB_SERIAL install -r app/build/outputs/apk/debug/app-debug.apk
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. This client is maintained
alongside the server and web application in the Autolycus repository. Quiet TV
can optionally build/install it using `AUTOLYCUS_REPO_DIR` and its external
`autolycus-tv` selector. Screen capture and ambient lighting belong to the separate
Ambient TV application, not this client.
Open Autolycus and enter its server's LAN address, including the port; use the
host address rather than `localhost`. First launch can alternatively receive a
`server_url` intent extra. Subsequent launches use the saved address.

## Assets and references

The icon paths are from Autolycus's bundled `ui/public/icons/autolycus-icon.svg`
(BiMeteor), converted to a native vector on neutral black. Upstream's GPL version
3 text is bundled in `app/src/main/assets/notices/AUTOLYCUS-GPL-3.0.txt`. This does
not assign a license to independently authored application or parent project code.
The AndroidX Media3 libraries retain their Apache 2.0 licensing.
Material play-arrow artwork retains the bundled Material Icons Apache 2.0 notice.

Android documents [supported media formats](https://developer.android.com/media/media3/exoplayer/supported-formats)
and the distinction between [TV UI and video resolution](https://developer.android.com/training/tv/playback/memory).
