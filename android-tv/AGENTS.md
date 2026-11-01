# Working on Autolycus TV

This is the standalone native Android TV movie client. Read README.md and
upstream.json; preserve existing server/web/native changes. Keep modifications
inside this project when possible. Ambient screen capture belongs to its own app.

For every installation or update, select one authorized TV, preserve package
signature, authentication, server URL, profile and playback preferences, and use
`adb install -r`. Do not clear data, uninstall or reboot without explicit owner
authorization. Honour explicit session instructions about backups.

Inspect the owner's existing Quiet TV Home routing before and after updates and
maintenance force-stops: HOME resolver, narrow accessibility-service binding,
accessibility-enabled state, AUTO_START and saved Home toggle. Restore only
previously authorized settings changed by the work. Preserve other services and
the working animation-free redirect; never disable Google TV/setup services.
Check repeated Home presses and Home from this app, with remote coordination and
actual screenshot inspection. Verify unchanged boot_count and saved favourites.
Avoid explicitly force-stopping Quiet TV: Android 14 removes its accessibility
service from the enabled list. If unavoidable, restore its previously authorized
selection and immediately verify Home; launching HomeActivity is insufficient.

Run tools/test-local.sh, assembleDebug and lintDebug. For visible changes, inject
appropriate D-pad input and inspect screenshots for focus, clipping and icons.
For Watch Next changes, verify actual provider publication and a launcher card
resuming the correct title/position in the current authenticated profile. Confirm
completed/unavailable titles are removed. Do not expose server credentials,
private media paths or signed artwork URLs in provider metadata or test output.

Keep screenshots, logs, tokens, signing keys and APKs untracked. Report measured
results and limitations; installation/compilation alone is not playback testing.
