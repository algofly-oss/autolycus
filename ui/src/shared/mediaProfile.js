let selected = "default";
export const activeMediaProfile = () => selected;
export const setActiveMediaProfile = value => { selected = value || "default"; };
export const profileHeaders = () => ({"X-Profile-ID":selected});
export const PROFILE_PREF_KEYS = ["home_view_mode","search_view_mode","video_quality","video_subtitles","video_audio_language"];
