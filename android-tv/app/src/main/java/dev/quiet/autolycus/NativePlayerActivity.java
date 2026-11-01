package dev.quiet.autolycus;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.ClipDrawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.LayerDrawable;
import android.graphics.drawable.StateListDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.SurfaceView;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.Format;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.TrackSelectionOverride;
import androidx.media3.common.Tracks;
import androidx.media3.common.VideoSize;
import androidx.media3.datasource.DataSource;
import androidx.media3.exoplayer.DecoderCounters;
import androidx.media3.exoplayer.DefaultLoadControl;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.analytics.AnalyticsListener;
import androidx.media3.exoplayer.audio.AudioSink;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.ui.AspectRatioFrameLayout;
import androidx.media3.ui.CaptionStyleCompat;
import androidx.media3.ui.PlayerView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Original-byte native playback with a SurfaceView and TV-first controls. */
@androidx.annotation.OptIn(markerClass = androidx.media3.common.util.UnstableApi.class)
public final class NativePlayerActivity extends Activity {
    private static final String TAG = "AutolycusPlayer";
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService network = Executors.newFixedThreadPool(2);
    private AutolycusApi api;
    private JSONObject item, mediaInfo = new JSONObject(), donorSelection;
    private JSONArray files = new JSONArray(),
            versions = new JSONArray(),
            sidecars = new JSONArray();
    private String currentPath, originalPath, sourceUrl, decoder = "", quality = "Original";
    private String externalSubtitle = "", externalSubtitleMime = MimeTypes.APPLICATION_SUBRIP;
    private ExoPlayer player, donor;
    private PlayerView video;
    private FrameLayout overlay;
    private LinearLayout top, bottom;
    private TextView title, subtitle, time, durationLabel, notice, previewTime;
    private ImageButton play, mute;
    private Dialog menuDialog;
    private ProgressBar loading;
    private SeekBar timeline;
    private View lastPlaybackControl;
    private Runnable nextMenuParent;
    private long lastSeekKeyAt;
    private NativePlayerPreview preview;
    private boolean controls = true, dragging, autoNext = true, remote, resumed, destroyed, fill;
    private boolean firstFrame;
    private float volume = 1f;
    private long openedAt, lastSaved, lastDonorSync;
    private int generation;
    private AtomicBoolean alignmentCancelled;
    private final NativePlayerDataSource.Stats transferStats = new NativePlayerDataSource.Stats();
    private long diagnosticAt, diagnosticBytes;
    private int droppedFrames, rebufferCount;
    private NativePlayerAudioRoute audioRoute;
    private int sinkEncoding, sinkSampleRate, sinkChannelConfig;
    private boolean sinkOffload, sinkTunneling;
    private String audioDecoder = "";
    private JSONObject pendingSubtitle;
    private final Runnable hideControls = () -> setControls(false);
    private final Runnable tick =
            new Runnable() {
                @Override
                public void run() {
                    if (destroyed || player == null || !resumed) return;
                    updateTimeline();
                    writeDiagnostics();
                    syncDonor(false);
                    saveProgress(false);
                    main.postDelayed(this, 500);
                }
            };

    public static void open(
            Activity activity, JSONObject item, String path, String server, String profile) {
        Intent intent = new Intent(activity, NativePlayerActivity.class);
        intent.putExtra("item", item.toString());
        intent.putExtra("path", path);
        intent.putExtra("server", server);
        intent.putExtra("profile", profile);
        activity.startActivity(intent);
    }

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.native_player);
        immersive();
        try {
            item = new JSONObject(getIntent().getStringExtra("item"));
        } catch (Exception invalid) {
            finish();
            return;
        }
        api = new AutolycusApi(this, getIntent().getStringExtra("server"));
        api.setProfile(getIntent().getStringExtra("profile"));
        files = item.optJSONArray("files") == null ? new JSONArray() : item.optJSONArray("files");
        autoNext = getSharedPreferences("native-player", MODE_PRIVATE).getBoolean("autoNext", true);
        video = findViewById(R.id.native_player_surface);
        overlay = findViewById(R.id.native_player_overlay);
        if (!(video.getVideoSurfaceView() instanceof SurfaceView))
            throw new IllegalStateException("HDR playback requires SurfaceView");
        createControls();
        DataSource.Factory data = () -> new NativePlayerDataSource(api, transferStats);
        audioRoute = new NativePlayerAudioRoute(this);
        player =
                new ExoPlayer.Builder(this, audioRoute.renderers(this))
                        .setMediaSourceFactory(new DefaultMediaSourceFactory(data))
                        .setLoadControl(
                                new DefaultLoadControl.Builder()
                                        .setBufferDurationsMs(5000, 30000, 500, 1500)
                                        .setTargetBufferBytes(32 * 1024 * 1024)
                                        .setPrioritizeTimeOverSizeThresholds(false)
                                        .build())
                        .build();
        player.setTrackSelectionParameters(
                player.getTrackSelectionParameters()
                        .buildUpon()
                        .clearVideoSizeConstraints()
                        .clearViewportSizeConstraints()
                        .setForceHighestSupportedBitrate(true)
                        .build());
        player.setAudioAttributes(
                new AudioAttributes.Builder()
                        .setUsage(C.USAGE_MEDIA)
                        .setContentType(C.AUDIO_CONTENT_TYPE_MOVIE)
                        .build(),
                true);
        player.setHandleAudioBecomingNoisy(true);
        video.setPlayer(player);
        if (video.getSubtitleView() != null) {
            video.getSubtitleView()
                    .setStyle(
                            new CaptionStyleCompat(
                                    Color.WHITE,
                                    Color.TRANSPARENT,
                                    Color.TRANSPARENT,
                                    CaptionStyleCompat.EDGE_TYPE_DROP_SHADOW,
                                    Color.BLACK,
                                    Typeface.create("sans-serif-medium", Typeface.NORMAL)));
            video.getSubtitleView().setFractionalTextSize(.035f);
        }
        player.addListener(
                new Player.Listener() {
                    @Override
                    public void onPlaybackStateChanged(int state) {
                        if (state == Player.STATE_BUFFERING && firstFrame) rebufferCount++;
                        loading.setVisibility(
                                state == Player.STATE_BUFFERING ? View.VISIBLE : View.GONE);
                        if (state == Player.STATE_READY) {
                            notice.setVisibility(View.GONE);
                            updateTimeline();
                        }
                        if (state == Player.STATE_ENDED) {
                            saveProgress(true);
                            if (autoNext) nextEpisode(1);
                            else setControls(true);
                        }
                    }

                    @Override
                    public void onIsPlayingChanged(boolean playing) {
                        play.setImageResource(
                                playing
                                        ? R.drawable.native_player_pause
                                        : R.drawable.native_player_play);
                        play.setContentDescription(playing ? "Pause" : "Play");
                        if (!playing) saveProgress(true);
                        else scheduleHide();
                        syncDonor(true);
                    }

                    @Override
                    public void onPlayerError(PlaybackException error) {
                        loading.setVisibility(View.GONE);
                        notice.setText(
                                "Unable to play this source on the TV.\n"
                                        + error.getErrorCodeName()
                                        + "\nOpen Settings to retry or choose another source.");
                        notice.setVisibility(View.VISIBLE);
                        setControls(true);
                        Log.w(TAG, "playback_error=" + error.getErrorCodeName());
                    }

                    @Override
                    public void onVideoSizeChanged(VideoSize size) {
                        updateSubtitle();
                    }

                    @Override
                    public void onTracksChanged(Tracks tracks) {
                        updateSubtitle();
                        if (pendingSubtitle != null) restoreSubtitle(pendingSubtitle);
                    }
                });
        player.addAnalyticsListener(
                new AnalyticsListener() {
                    @Override
                    public void onVideoDecoderInitialized(
                            EventTime time, String name, long timestamp, long duration) {
                        decoder = name;
                        Log.i(TAG, "decoder=" + name);
                    }

                    @Override
                    public void onDroppedVideoFrames(EventTime time, int count, long elapsedMs) {
                        droppedFrames += count;
                    }

                    @Override
                    public void onAudioDecoderInitialized(
                            EventTime time, String name, long timestamp, long duration) {
                        audioDecoder = name;
                    }

                    @Override
                    public void onAudioTrackInitialized(
                            EventTime time, AudioSink.AudioTrackConfig config) {
                        sinkEncoding = config.encoding;
                        sinkSampleRate = config.sampleRate;
                        sinkChannelConfig = config.channelConfig;
                        sinkOffload = config.offload;
                        sinkTunneling = config.tunneling;
                    }

                    @Override
                    public void onRenderedFirstFrame(
                            EventTime time, Object output, long renderedTimeMs) {
                        firstFrame = true;
                        Format format = player.getVideoFormat();
                        getSharedPreferences("native-player-diagnostics", MODE_PRIVATE)
                                .edit()
                                .putLong("firstFrameMs", SystemClock.elapsedRealtime() - openedAt)
                                .putInt("videoWidth", format == null ? 0 : format.width)
                                .putInt("videoHeight", format == null ? 0 : format.height)
                                .putString("videoMime", format == null ? "" : format.sampleMimeType)
                                .putString("decoder", decoder)
                                .putInt(
                                        "colorTransfer",
                                        format == null || format.colorInfo == null
                                                ? -1
                                                : format.colorInfo.colorTransfer)
                                .apply();
                        Log.i(
                                TAG,
                                "first_frame_ms="
                                        + (SystemClock.elapsedRealtime() - openedAt)
                                        + " decoded="
                                        + (format == null
                                                ? "unknown"
                                                : format.width + "x" + format.height)
                                        + " mime="
                                        + (format == null ? "unknown" : format.sampleMimeType)
                                        + " color_transfer="
                                        + (format == null || format.colorInfo == null
                                                ? -1
                                                : format.colorInfo.colorTransfer));
                        scheduleHide();
                    }
                });
        String path = getIntent().getStringExtra("path");
        if (path == null || path.isEmpty())
            path = item.optString("resume_path", item.optString("path"));
        loadPath(path, resumeFor(path));
    }

    private void createControls() {
        loading = new ProgressBar(this);
        FrameLayout.LayoutParams loadingPosition =
                new FrameLayout.LayoutParams(dp(48), dp(48), Gravity.CENTER);
        overlay.addView(loading, loadingPosition);
        notice = label("", 18, Color.WHITE);
        notice.setGravity(Gravity.CENTER);
        notice.setPadding(dp(40), dp(20), dp(40), dp(20));
        notice.setVisibility(View.GONE);
        FrameLayout.LayoutParams errorPosition =
                new FrameLayout.LayoutParams(-1, -2, Gravity.CENTER);
        overlay.addView(notice, errorPosition);
        top = new LinearLayout(this);
        top.setOrientation(LinearLayout.VERTICAL);
        top.setPadding(dp(26), dp(14), dp(26), dp(22));
        top.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.TOP_BOTTOM,
                        new int[] {0xb8000000, 0x00000000}));
        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        titleRow.setPadding(0, dp(4), 0, dp(4));
        titleRow.setClipChildren(false);
        titleRow.setClipToPadding(false);
        title = label(item.optString("title", "Autolycus"), 16, Color.WHITE);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        title.setSingleLine(true);
        title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        titleRow.addView(title, new LinearLayout.LayoutParams(0, dp(40), 1));
        title.setGravity(Gravity.CENTER_VERTICAL);
        top.addView(titleRow);
        subtitle = label("Original · Connecting", 12, 0xffbac1cd);
        subtitle.setPadding(0, dp(7), 0, 0);
        subtitle.setVisibility(View.GONE);
        top.addView(subtitle);
        overlay.addView(top, new FrameLayout.LayoutParams(-1, -2, Gravity.TOP));
        bottom = new LinearLayout(this);
        bottom.setOrientation(LinearLayout.VERTICAL);
        bottom.setPadding(dp(26), dp(32), dp(26), dp(16));
        bottom.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.TOP_BOTTOM,
                        new int[] {0x00000000, 0xdb000000}));
        LinearLayout timelineRow = new LinearLayout(this);
        timelineRow.setGravity(Gravity.CENTER_VERTICAL);
        timeline = new SeekBar(this);
        timeline.setMax(10000);
        timeline.setContentDescription("Playback position. Left and right seek ten seconds.");
        timeline.setProgressTintList(android.content.res.ColorStateList.valueOf(Color.WHITE));
        timeline.setThumbTintList(android.content.res.ColorStateList.valueOf(Color.WHITE));
        styleTimeline();
        timelineRow.addView(timeline, new LinearLayout.LayoutParams(-1, dp(28)));
        timeline.setOnKeyListener(
                (view, key, event) -> {
                    if (key == KeyEvent.KEYCODE_DPAD_DOWN && lastPlaybackControl != null) {
                        if (event.getAction() == KeyEvent.ACTION_DOWN)
                            lastPlaybackControl.requestFocus();
                        return true;
                    }
                    if (key == KeyEvent.KEYCODE_DPAD_LEFT || key == KeyEvent.KEYCODE_DPAD_RIGHT) {
                        if (event.getAction() == KeyEvent.ACTION_DOWN
                                && (event.getRepeatCount() == 0
                                        || event.getEventTime() - lastSeekKeyAt >= 200)) {
                            lastSeekKeyAt = event.getEventTime();
                            long held = event.getEventTime() - event.getDownTime();
                            long step = held >= 3000 ? 60000 : held >= 1500 ? 30000 : 10000;
                            seek(key == KeyEvent.KEYCODE_DPAD_RIGHT ? step : -step);
                        }
                        return true;
                    }
                    return false;
                });
        timeline.setOnSeekBarChangeListener(
                new SeekBar.OnSeekBarChangeListener() {
                    @Override
                    public void onProgressChanged(SeekBar bar, int value, boolean user) {
                        if (user && validDuration())
                            showPreview(player.getDuration() * value / 10000);
                    }

                    @Override
                    public void onStartTrackingTouch(SeekBar bar) {
                        dragging = true;
                        main.removeCallbacks(hideControls);
                    }

                    @Override
                    public void onStopTrackingTouch(SeekBar bar) {
                        dragging = false;
                        if (validDuration()) {
                            player.seekTo(player.getDuration() * bar.getProgress() / 10000);
                            syncDonor(true);
                            saveProgress(true);
                        }
                        hidePreview();
                        scheduleHide();
                    }
                });
        bottom.addView(timelineRow);
        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        actions.setPadding(0, dp(6), 0, dp(6));
        actions.setClipChildren(false);
        actions.setClipToPadding(false);
        if ("series".equals(item.optString("kind")) && files.length() > 1)
            actions.addView(
                    iconButton(
                            R.drawable.native_player_previous,
                            "Previous episode",
                            () -> nextEpisode(-1)));
        play = iconButton(R.drawable.native_player_pause, "Pause", this::togglePlay);
        actions.addView(play);
        if ("series".equals(item.optString("kind")) && files.length() > 1)
            actions.addView(
                    iconButton(
                            R.drawable.native_player_next, "Next episode", () -> nextEpisode(1)));
        mute =
                iconButton(
                        R.drawable.native_player_volume,
                        "Mute",
                        () -> {
                            volume = volume == 0 ? 1 : 0;
                            mute.setImageResource(
                                    volume == 0
                                            ? R.drawable.native_player_muted
                                            : R.drawable.native_player_volume);
                            mute.setContentDescription(volume == 0 ? "Unmute" : "Mute");
                            mute.setTooltipText(volume == 0 ? "Unmute" : "Mute");
                            player.setVolume(donor == null ? volume : 0);
                            if (donor != null) donor.setVolume(volume);
                        });
        actions.addView(mute);
        time = label("0:00", 12, Color.WHITE);
        time.setPadding(dp(12), 0, dp(7), 0);
        actions.addView(time);
        TextView separator = label("/", 12, 0xff999ca2);
        actions.addView(separator);
        durationLabel = label("0:00", 12, 0xffc2c4ca);
        durationLabel.setPadding(dp(7), 0, 0, 0);
        actions.addView(durationLabel);
        View spacer = new View(this);
        actions.addView(spacer, new LinearLayout.LayoutParams(0, 1, 1));
        actions.addView(
                iconButton(R.drawable.native_player_subtitles, "Subtitles", this::showSubtitles));
        if ("series".equals(item.optString("kind")) && files.length() > 1)
            actions.addView(
                    iconButton(R.drawable.native_player_episodes, "Episodes", this::showEpisodes));
        actions.addView(
                iconButton(R.drawable.native_player_settings, "Settings", this::showSettings));
        bottom.addView(actions);
        overlay.addView(bottom, new FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM));
        preview = new NativePlayerPreview(this, api, network);
        FrameLayout.LayoutParams previewPosition =
                new FrameLayout.LayoutParams(
                        dp(192), dp(108), Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        previewPosition.bottomMargin = dp(126);
        preview.setVisibility(View.GONE);
        overlay.addView(preview, previewPosition);
        previewTime = label("", 14, Color.WHITE);
        previewTime.setGravity(Gravity.CENTER);
        FrameLayout.LayoutParams previewTimePosition =
                new FrameLayout.LayoutParams(
                        dp(192), dp(28), Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        previewTimePosition.bottomMargin = dp(98);
        previewTime.setVisibility(View.GONE);
        overlay.addView(previewTime, previewTimePosition);
    }

    private TextView button(String text, Runnable action) {
        TextView button = label(text, 14, Color.WHITE);
        button.setText(text);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(16), dp(11), dp(16), dp(11));
        button.setFocusable(true);
        button.setClickable(true);
        button.setContentDescription(text);
        LinearLayout.LayoutParams position = new LinearLayout.LayoutParams(-2, dp(44));
        position.setMargins(dp(3), dp(3), dp(3), dp(3));
        button.setLayoutParams(position);
        button.setOnFocusChangeListener(
                (view, focused) -> {
                    GradientDrawable shape = new GradientDrawable();
                    shape.setCornerRadius(dp(7));
                    shape.setColor(focused ? Color.WHITE : 0x25ffffff);
                    button.setBackground(shape);
                    button.setTextColor(focused ? Color.BLACK : Color.WHITE);
                    if (focused) main.removeCallbacks(hideControls);
                });
        GradientDrawable shape = new GradientDrawable();
        shape.setCornerRadius(dp(7));
        shape.setColor(0x25ffffff);
        button.setBackground(shape);
        button.setOnClickListener(
                view -> {
                    action.run();
                    scheduleHide();
                });
        return button;
    }

    private ImageButton iconButton(int resource, String label, Runnable action) {
        ImageButton button = new ImageButton(this);
        button.setImageResource(resource);
        button.setContentDescription(label);
        button.setTooltipText(label);
        button.setBackgroundColor(Color.TRANSPARENT);
        button.setPadding(dp(10), dp(10), dp(10), dp(10));
        button.setFocusable(true);
        button.setClickable(true);
        button.setOnKeyListener(
                (view, key, event) -> {
                    if (key == KeyEvent.KEYCODE_DPAD_UP) {
                        if (event.getAction() == KeyEvent.ACTION_DOWN) {
                            lastPlaybackControl = view;
                            timeline.requestFocus();
                        }
                        return true;
                    }
                    return false;
                });
        LinearLayout.LayoutParams size = new LinearLayout.LayoutParams(dp(42), dp(42));
        size.setMargins(dp(2), 0, dp(2), 0);
        button.setLayoutParams(size);
        button.setOnFocusChangeListener(
                (view, focused) -> {
                    GradientDrawable background = new GradientDrawable();
                    background.setShape(GradientDrawable.OVAL);
                    background.setColor(focused ? 0x38ffffff : Color.TRANSPARENT);
                    button.setBackground(background);
                    button.animate()
                            .scaleX(focused ? 1.08f : 1f)
                            .scaleY(focused ? 1.08f : 1f)
                            .setDuration(120)
                            .start();
                    if (focused) main.removeCallbacks(hideControls);
                });
        button.setOnClickListener(
                view -> {
                    nextMenuParent = null;
                    action.run();
                    scheduleHide();
                });
        return button;
    }

    private void styleTimeline() {
        GradientDrawable background = new GradientDrawable();
        background.setColor(0x45ffffff);
        background.setCornerRadius(dp(2));
        background.setSize(dp(1), dp(2));
        GradientDrawable buffered = new GradientDrawable();
        buffered.setColor(0x70ffffff);
        buffered.setCornerRadius(dp(2));
        buffered.setSize(dp(1), dp(2));
        GradientDrawable foreground = new GradientDrawable();
        foreground.setColor(Color.WHITE);
        foreground.setCornerRadius(dp(2));
        foreground.setSize(dp(1), dp(2));
        LayerDrawable layers =
                new LayerDrawable(
                        new android.graphics.drawable.Drawable[] {
                            background,
                            new ClipDrawable(buffered, Gravity.LEFT, ClipDrawable.HORIZONTAL),
                            new ClipDrawable(foreground, Gravity.LEFT, ClipDrawable.HORIZONTAL)
                        });
        layers.setId(0, android.R.id.background);
        layers.setId(1, android.R.id.secondaryProgress);
        layers.setId(2, android.R.id.progress);
        timeline.setProgressDrawable(layers);
        timeline.setMinHeight(dp(2));
        timeline.setMaxHeight(dp(2));
        StateListDrawable thumb = new StateListDrawable();
        GradientDrawable large = new GradientDrawable();
        large.setShape(GradientDrawable.OVAL);
        large.setColor(Color.WHITE);
        large.setSize(dp(11), dp(11));
        GradientDrawable small = new GradientDrawable();
        small.setShape(GradientDrawable.OVAL);
        small.setColor(Color.WHITE);
        small.setSize(dp(7), dp(7));
        thumb.addState(new int[] {android.R.attr.state_focused}, large);
        thumb.addState(new int[] {}, new android.graphics.drawable.InsetDrawable(small, dp(2)));
        timeline.setThumb(thumb);
        timeline.setThumbOffset(dp(6));
        timeline.setPadding(dp(6), 0, dp(6), 0);
    }

    private TextView label(String value, int size, int color) {
        TextView label = new TextView(this);
        label.setText(value);
        label.setTextSize(size);
        label.setTextColor(color);
        return label;
    }

    private void loadPath(String path, long seekMs) {
        if (path == null || path.isEmpty()) {
            notice.setText("This title has no playable source.");
            notice.setVisibility(View.VISIBLE);
            return;
        }
        saveProgress(true);
        stopDonor();
        originalPath = path;
        if (path.contains("/api/files/stream?"))
            originalPath = Uri.parse(path).getQueryParameter("path");
        currentPath = originalPath;
        remote =
                originalPath.startsWith("/api/")
                        || originalPath.startsWith("http:")
                        || originalPath.startsWith("https:");
        externalSubtitle = "";
        pendingSubtitle = null;
        quality = "Original";
        versions = new JSONArray();
        sidecars = new JSONArray();
        mediaInfo = new JSONObject();
        int request = ++generation;
        title.setText(episodeTitle());
        preview.setPath(remote ? null : originalPath);
        prepareMedia(mediaUrl(originalPath), seekMs, true);
        final String loadingPath = originalPath;
        network.execute(
                () -> {
                    try {
                        JSONObject info = api.get(infoUrl(loadingPath));
                        JSONObject bookmark =
                                remote
                                        ? null
                                        : api.get(
                                                        "/api/files/playback/progress?path="
                                                                + encoded(loadingPath))
                                                .optJSONObject("progress");
                        JSONObject selected =
                                remote
                                        ? null
                                        : api.get(
                                                        "/api/files/playback/subtitle-selection?path="
                                                                + encoded(loadingPath))
                                                .optJSONObject("selection");
                        JSONObject soundtrack =
                                remote
                                        ? null
                                        : api.get(
                                                        "/api/files/playback/alternate-audio?path="
                                                                + encoded(loadingPath))
                                                .optJSONObject("selection");
                        main.post(
                                () -> {
                                    if (destroyed || request != generation) return;
                                    mediaInfo = info;
                                    versions =
                                            info.optJSONArray("versions") == null
                                                    ? new JSONArray()
                                                    : info.optJSONArray("versions");
                                    sidecars =
                                            info.optJSONArray("subtitles") == null
                                                    ? new JSONArray()
                                                    : info.optJSONArray("subtitles");
                                    if (bookmark != null
                                            && !bookmark.optBoolean("completed")
                                            && player.getCurrentPosition() < 2500
                                            && seekMs <= 0)
                                        player.seekTo(
                                                (long) (bookmark.optDouble("position") * 1000));
                                    if (selected != null
                                            && !selected.optString("subtitle").isEmpty())
                                        restoreSubtitle(selected);
                                    restorePrivateSubtitle(loadingPath);
                                    if (soundtrack != null
                                            && !soundtrack.optString("donor").isEmpty())
                                        openDonor(preferredSoundtrack(soundtrack));
                                });
                    } catch (Exception ignored) {
                        /* A metadata failure does not stop the original byte stream. */
                    }
                });
    }

    private void prepareMedia(String url, long position, boolean playWhenReady) {
        if (!NativePlayerDataSource.sameOrigin(api.getServer(), url)) {
            notice.setText("Choose a source provided by the configured Autolycus server.");
            notice.setVisibility(View.VISIBLE);
            return;
        }
        sourceUrl = url;
        firstFrame = false;
        getSharedPreferences("native-player-diagnostics", MODE_PRIVATE)
                .edit()
                .putLong("firstFrameMs", 0)
                .putBoolean("renderedFirstFrame", false)
                .apply();
        droppedFrames = 0;
        rebufferCount = 0;
        diagnosticAt = 0;
        diagnosticBytes = transferStats.bytes.get();
        openedAt = SystemClock.elapsedRealtime();
        MediaItem.Builder media = new MediaItem.Builder().setUri(url);
        if (!externalSubtitle.isEmpty()) {
            MediaItem.SubtitleConfiguration track =
                    new MediaItem.SubtitleConfiguration.Builder(Uri.parse(externalSubtitle))
                            .setMimeType(externalSubtitleMime)
                            .setSelectionFlags(C.SELECTION_FLAG_DEFAULT)
                            .setLabel("Selected subtitles")
                            .build();
            media.setSubtitleConfigurations(java.util.Collections.singletonList(track));
        }
        player.setMediaItem(media.build(), Math.max(0, position));
        player.prepare();
        player.setPlayWhenReady(playWhenReady);
        loading.setVisibility(View.VISIBLE);
        setControls(true);
        play.requestFocus();
    }

    private String mediaUrl(String path) {
        return api.absolute(
                path.startsWith("/api/") || path.startsWith("http:") || path.startsWith("https:")
                        ? path
                        : "/api/files/stream?path=" + encoded(path));
    }

    private String infoUrl(String path) {
        return remote ? path + "/info" : "/api/files/playback/info?path=" + encoded(path);
    }

    private long resumeFor(String path) {
        JSONObject progress = item.optJSONObject("progress");
        if (progress != null
                && !progress.optBoolean("completed")
                && path.equals(progress.optString("path")))
            return (long) (progress.optDouble("position") * 1000);
        return getSharedPreferences("native-player", MODE_PRIVATE)
                .getLong(localBookmarkKey(path), 0);
    }

    private String episodeTitle() {
        JSONObject file = currentFile();
        String series = item.optString("title", "Autolycus");
        if (!"series".equals(item.optString("kind")) || file == null) return series;
        String episode = file.optString("display_name", file.optString("name"));
        String normalizedSeries = series.replaceAll("[.\\s]+", " ").trim();
        String normalizedEpisode = episode.replaceAll("[.\\s]+", " ").trim();
        return normalizedEpisode.regionMatches(
                        true, 0, normalizedSeries, 0, normalizedSeries.length())
                ? episode
                : series + " · " + episode;
    }

    private JSONObject currentFile() {
        for (int i = 0; i < files.length(); i++) {
            JSONObject entry = files.optJSONObject(i);
            if (entry != null && originalPath.equals(entry.optString("path"))) return entry;
        }
        return null;
    }

    private void togglePlay() {
        if (player.isPlaying()) player.pause();
        else player.play();
    }

    private void seek(long delta) {
        if (!validDuration()) return;
        long position =
                Math.max(
                        0, Math.min(player.getDuration() - 1, player.getCurrentPosition() + delta));
        player.seekTo(position);
        syncDonor(true);
        showPreview(position);
        main.removeCallbacks(hideControls);
        main.postDelayed(this::hidePreview, 2000);
        main.postDelayed(hideControls, 3500);
        updateTimeline();
        saveProgress(true);
    }

    private void showPreview(long position) {
        if (remote) return;
        preview.showPosition(position);
        previewTime.setText(clock(position));
        previewTime.setVisibility(View.VISIBLE);
    }

    private void hidePreview() {
        preview.hide();
        previewTime.setVisibility(View.GONE);
    }

    private void updateTimeline() {
        if (!validDuration()) return;
        long position = player.getCurrentPosition(), duration = player.getDuration();
        time.setText(clock(position));
        durationLabel.setText(clock(duration));
        if (!dragging) timeline.setProgress((int) (10000 * position / duration));
        timeline.setSecondaryProgress(
                (int) Math.min(10000, 10000 * player.getBufferedPosition() / duration));
    }

    private void writeDiagnostics() {
        if (!BuildConfig.DEBUG || player == null) return;
        long now = SystemClock.elapsedRealtime();
        if (now - diagnosticAt < 2000) return;
        long bytes = transferStats.bytes.get();
        float throughput =
                diagnosticAt == 0
                        ? 0
                        : (bytes - diagnosticBytes) * 8f / Math.max(1, now - diagnosticAt) / 1000f;
        Format format = player.getVideoFormat();
        DecoderCounters counters = player.getVideoDecoderCounters();
        Format audioFormat = player.getAudioFormat();
        if (counters != null) counters.ensureUpdated();
        getSharedPreferences("native-player-diagnostics", MODE_PRIVATE)
                .edit()
                .putLong("sampleAtElapsedMs", now)
                .putInt("playbackState", player.getPlaybackState())
                .putBoolean("isPlaying", player.isPlaying())
                .putBoolean("playWhenReady", player.getPlayWhenReady())
                .putFloat("requestedVolume", volume)
                .putFloat("playerVolume", player.getVolume())
                .putFloat("donorVolume", donor == null ? -1 : donor.getVolume())
                .putLong("posMs", player.getCurrentPosition())
                .putLong("bufferedMs", player.getBufferedPosition())
                .putLong("bufferedDurationMs", player.getTotalBufferedDuration())
                .putInt("videoWidth", format == null ? 0 : format.width)
                .putInt("videoHeight", format == null ? 0 : format.height)
                .putString("videoMime", format == null ? "" : format.sampleMimeType)
                .putString("decoder", decoder)
                .putInt(
                        "colorTransfer",
                        format == null || format.colorInfo == null
                                ? -1
                                : format.colorInfo.colorTransfer)
                .putInt("droppedFrames", droppedFrames)
                .putString("audioMime", audioFormat == null ? "" : audioFormat.sampleMimeType)
                .putInt("audioChannelCount", audioFormat == null ? 0 : audioFormat.channelCount)
                .putInt("audioSampleRate", audioFormat == null ? 0 : audioFormat.sampleRate)
                .putString("audioDecoder", audioDecoder)
                .putBoolean("bluetoothPcmSink", audioRoute != null && audioRoute.bluetooth)
                .putString("audioRouteTypes", audioRoute == null ? "" : audioRoute.routeTypes)
                .putInt("audioSinkEncoding", sinkEncoding)
                .putInt("audioSinkSampleRate", sinkSampleRate)
                .putInt("audioSinkChannelConfig", sinkChannelConfig)
                .putBoolean("audioSinkOffload", sinkOffload)
                .putBoolean("audioSinkTunneling", sinkTunneling)
                .putBoolean("renderedFirstFrame", firstFrame)
                .putLong("openAtElapsedMs", openedAt)
                .putInt(
                        "renderedVideoBuffers",
                        counters == null ? 0 : counters.renderedOutputBufferCount)
                .putInt("droppedVideoBuffers", counters == null ? 0 : counters.droppedBufferCount)
                .putInt(
                        "skippedVideoBuffers",
                        counters == null ? 0 : counters.skippedOutputBufferCount)
                .putInt(
                        "maxConsecutiveDroppedVideoBuffers",
                        counters == null ? 0 : counters.maxConsecutiveDroppedBufferCount)
                .putInt("rebufferCount", rebufferCount)
                .putLong("mediaBytesRead", bytes)
                .putFloat("recentReadMbps", throughput)
                .putLong("mediaHttpRequests", transferStats.requests.get())
                .putLong("lastRequestedBytePosition", transferStats.lastRequestedPosition.get())
                .putLong("lastReadAtElapsedMs", transferStats.lastReadAt.get())
                .apply();
        diagnosticAt = now;
        diagnosticBytes = bytes;
    }

    private boolean validDuration() {
        return player != null && player.getDuration() > 0 && player.getDuration() != C.TIME_UNSET;
    }

    private void updateSubtitle() {
        Format format = player.getVideoFormat();
        if (format == null) {
            subtitle.setText(quality + " · Connecting");
            return;
        }
        String transfer =
                format.colorInfo == null
                        ? ""
                        : format.colorInfo.colorTransfer == C.COLOR_TRANSFER_ST2084
                                ? " · HDR PQ"
                                : format.colorInfo.colorTransfer == C.COLOR_TRANSFER_HLG
                                        ? " · HLG"
                                        : "";
        if (MimeTypes.VIDEO_DOLBY_VISION.equals(format.sampleMimeType))
            transfer = " · Dolby Vision stream";
        subtitle.setText(
                quality
                        + " · "
                        + format.width
                        + " × "
                        + format.height
                        + (format.frameRate > 0
                                ? " · " + Math.round(format.frameRate) + " fps"
                                : "")
                        + transfer);
    }

    private void setControls(boolean visible) {
        controls = visible;
        top.setVisibility(visible ? View.VISIBLE : View.GONE);
        bottom.setVisibility(visible ? View.VISIBLE : View.GONE);
        if (!visible) {
            hidePreview();
            overlay.setFocusableInTouchMode(true);
            overlay.requestFocus();
        } else scheduleHide();
    }

    private void scheduleHide() {
        main.removeCallbacks(hideControls);
        if (player != null
                && player.isPlaying()
                && !dragging
                && (menuDialog == null || !menuDialog.isShowing()))
            main.postDelayed(hideControls, 4000);
    }

    private void saveProgress(boolean force) {
        if (!validDuration()
                || originalPath == null
                || player.getPlaybackState() == Player.STATE_IDLE) return;
        long now = SystemClock.elapsedRealtime();
        if (!force && now - lastSaved < 10000) return;
        lastSaved = now;
        long position = player.getCurrentPosition(), duration = player.getDuration();
        boolean completed =
                player.getPlaybackState() == Player.STATE_ENDED || duration - position < 2000;
        getSharedPreferences("native-player", MODE_PRIVATE)
                .edit()
                .putLong(localBookmarkKey(originalPath), completed ? 0 : position)
                .apply();
        if (!remote)
            NativeWatchNext.progress(this, api, item, originalPath, position, duration, completed);
        if (remote) return;
        JSONObject progress = new JSONObject();
        put(progress, "path", originalPath);
        put(progress, "position", position / 1000d);
        put(progress, "duration", duration / 1000d);
        put(progress, "completed", completed);
        if (!network.isShutdown())
            network.execute(
                    () -> {
                        try {
                            api.post("/api/files/playback/progress", progress);
                        } catch (Exception ignored) {
                        }
                    });
    }

    private void nextEpisode(int direction) {
        if (!"series".equals(item.optString("kind"))) {
            if (direction > 0 && player.getPlaybackState() == Player.STATE_ENDED) setControls(true);
            return;
        }
        int current = -1;
        for (int i = 0; i < files.length(); i++)
            if (files.optJSONObject(i) != null
                    && originalPath.equals(files.optJSONObject(i).optString("path"))) current = i;
        int next = current + direction;
        if (current >= 0 && next >= 0 && next < files.length())
            loadPath(files.optJSONObject(next).optString("path"), 0);
        else setControls(true);
    }

    private void showSettings() {
        nextMenuParent = null;
        main.removeCallbacks(hideControls);
        String[] options = {
            "Audio tracks",
            "Subtitles",
            "Quality · " + quality,
            "Playback speed",
            "Episodes",
            "Autoplay next · " + (autoNext ? "On" : "Off"),
            fill ? "Fit entire video" : "Fill screen",
            "Playback information",
            "External soundtrack",
            "Retry playback",
            "Sources"
        };
        menu(
                "Playback",
                options,
                which -> {
                    switch (which) {
                        case 0:
                            showAudioTracks();
                            break;
                        case 1:
                            showSubtitles();
                            break;
                        case 2:
                            showQuality();
                            break;
                        case 3:
                            showSpeed();
                            break;
                        case 4:
                            showEpisodes();
                            break;
                        case 5:
                            autoNext = !autoNext;
                            getSharedPreferences("native-player", MODE_PRIVATE)
                                    .edit()
                                    .putBoolean("autoNext", autoNext)
                                    .apply();
                            showSettings();
                            break;
                        case 6:
                            fill = !fill;
                            video.setResizeMode(
                                    fill
                                            ? AspectRatioFrameLayout.RESIZE_MODE_ZOOM
                                            : AspectRatioFrameLayout.RESIZE_MODE_FIT);
                            break;
                        case 7:
                            showInformation();
                            break;
                        case 8:
                            showSoundtrack();
                            break;
                        case 9:
                            prepareMedia(sourceUrl, player.getCurrentPosition(), true);
                            break;
                        case 10:
                            showSources();
                            break;
                        default:
                            break;
                    }
                });
    }

    private void showAudioTracks() {
        List<String> labels = new ArrayList<>();
        List<Runnable> actions = new ArrayList<>();
        for (Tracks.Group group : player.getCurrentTracks().getGroups()) {
            if (group.getType() != C.TRACK_TYPE_AUDIO) continue;
            for (int i = 0; i < group.length; i++) {
                final int track = i;
                Format format = group.getTrackFormat(i);
                labels.add(
                        (group.isTrackSelected(i) && donor == null ? "✓ " : "")
                                + trackName(format, i));
                actions.add(
                        () -> {
                            stopDonor();
                            player.setTrackSelectionParameters(
                                    player.getTrackSelectionParameters()
                                            .buildUpon()
                                            .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, false)
                                            .setOverrideForType(
                                                    new TrackSelectionOverride(
                                                            group.getMediaTrackGroup(), track))
                                            .build());
                            if (format.language != null)
                                network.execute(
                                        () -> {
                                            try {
                                                JSONObject p = new JSONObject();
                                                put(p, "video_audio_language", format.language);
                                                api.patch("/api/auth/preferences", p);
                                            } catch (Exception ignored) {
                                            }
                                        });
                        });
            }
        }
        if (labels.isEmpty()) {
            toast("No selectable audio track is available yet.");
            return;
        }
        menu("Audio", labels.toArray(new String[0]), which -> actions.get(which).run());
    }

    private void showSubtitles() {
        List<String> labels = new ArrayList<>();
        List<Runnable> actions = new ArrayList<>();
        labels.add("Off");
        actions.add(
                () -> {
                    player.setTrackSelectionParameters(
                            player.getTrackSelectionParameters()
                                    .buildUpon()
                                    .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true)
                                    .build());
                    persistSubtitle("", "en", "");
                });
        int groupIndex = 0;
        for (Tracks.Group group : player.getCurrentTracks().getGroups()) {
            if (group.getType() == C.TRACK_TYPE_TEXT)
                for (int i = 0; i < group.length; i++) {
                    final int track = i, ordinal = groupIndex;
                    Format format = group.getTrackFormat(i);
                    labels.add((group.isTrackSelected(i) ? "✓ " : "") + trackName(format, i));
                    actions.add(
                            () -> {
                                player.setTrackSelectionParameters(
                                        player.getTrackSelectionParameters()
                                                .buildUpon()
                                                .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                                                .setOverrideForType(
                                                        new TrackSelectionOverride(
                                                                group.getMediaTrackGroup(), track))
                                                .build());
                                Integer container = NativePlayerTrackIds.containerId(format.id);
                                String selection =
                                        container != null
                                                        && currentPath
                                                                .toLowerCase(Locale.ROOT)
                                                                .matches(".*\\.(mkv|webm)$")
                                                ? "mkv:" + container
                                                : "native:" + ordinal + ":" + track;
                                persistSubtitle(
                                        selection,
                                        language(format.language),
                                        trackName(format, track));
                            });
                }
            groupIndex++;
        }
        for (int i = 0; i < sidecars.length(); i++) {
            JSONObject entry = sidecars.optJSONObject(i);
            if (entry == null) continue;
            labels.add(entry.optString("name", "Subtitle file"));
            actions.add(
                    () ->
                            selectExternal(
                                    entry.optString("path"),
                                    entry.optString("language", "en"),
                                    entry.optString("name")));
        }
        if (!remote) {
            labels.add("Find subtitles…");
            actions.add(this::searchSubtitles);
        }
        menu("Subtitles", labels.toArray(new String[0]), which -> actions.get(which).run());
    }

    private void persistSubtitle(String path, String language, String name) {
        if (remote) return;
        pendingSubtitle = null;
        final String file = originalPath;
        JSONObject privateSelection = new JSONObject();
        put(privateSelection, "subtitle", path);
        put(privateSelection, "language", language);
        put(privateSelection, "name", name);
        if (path.startsWith("native:"))
            getSharedPreferences("native-player", MODE_PRIVATE)
                    .edit()
                    .putString("subtitle:" + localBookmarkKey(file), privateSelection.toString())
                    .apply();
        else
            getSharedPreferences("native-player", MODE_PRIVATE)
                    .edit()
                    .remove("subtitle:" + localBookmarkKey(file))
                    .apply();
        network.execute(
                () -> {
                    try {
                        JSONObject selected = new JSONObject();
                        put(selected, "path", file);
                        put(selected, "subtitle", path);
                        put(selected, "language", language);
                        put(selected, "name", name);
                        if (!path.startsWith("native:"))
                            api.put("/api/files/playback/subtitle-selection", selected);
                        JSONObject prefs = new JSONObject(), value = new JSONObject();
                        put(value, "enabled", !path.isEmpty());
                        put(value, "language", language);
                        put(value, "auto_match", true);
                        put(prefs, "video_subtitles", value);
                        api.patch("/api/auth/preferences", prefs);
                    } catch (Exception ignored) {
                    }
                });
    }

    private void restorePrivateSubtitle(String path) {
        String saved =
                getSharedPreferences("native-player", MODE_PRIVATE)
                        .getString("subtitle:" + localBookmarkKey(path), "");
        if (!saved.isEmpty())
            try {
                restoreSubtitle(new JSONObject(saved));
            } catch (JSONException ignored) {
            }
    }

    private void restoreSubtitle(JSONObject selection) {
        String value = selection.optString("subtitle");
        if (value.startsWith("native:") || value.startsWith("mkv:")) {
            pendingSubtitle = selection;
            String[] fields = value.split(":");
            int groupOrdinal = 0;
            for (Tracks.Group group : player.getCurrentTracks().getGroups()) {
                if (group.getType() == C.TRACK_TYPE_TEXT)
                    for (int i = 0; i < group.length; i++) {
                        boolean match =
                                value.startsWith("mkv:")
                                        ? value.substring(4).equals(group.getTrackFormat(i).id)
                                        : fields.length == 3
                                                && String.valueOf(groupOrdinal).equals(fields[1])
                                                && String.valueOf(i).equals(fields[2]);
                        if (!match) continue;
                        pendingSubtitle = null;
                        player.setTrackSelectionParameters(
                                player.getTrackSelectionParameters()
                                        .buildUpon()
                                        .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                                        .setOverrideForType(
                                                new TrackSelectionOverride(
                                                        group.getMediaTrackGroup(), i))
                                        .build());
                        return;
                    }
                groupOrdinal++;
            }
        } else if (!value.isEmpty()) {
            pendingSubtitle = null;
            selectExternal(
                    value, selection.optString("language", "en"), selection.optString("name"));
        }
    }

    private void selectExternal(String path, String language, String name) {
        externalSubtitle =
                api.absolute(
                        path.startsWith("os:")
                                ? "/api/files/playback/opensubtitles/file?path="
                                        + encoded(originalPath)
                                        + "&file_id="
                                        + encoded(path.substring(3))
                                : "/api/files/playback/subtitle?path=" + encoded(path));
        externalSubtitleMime =
                path.toLowerCase(Locale.ROOT).endsWith(".vtt")
                        ? MimeTypes.TEXT_VTT
                        : MimeTypes.APPLICATION_SUBRIP;
        long position = player.getCurrentPosition();
        boolean playing = player.getPlayWhenReady();
        player.setTrackSelectionParameters(
                player.getTrackSelectionParameters()
                        .buildUpon()
                        .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                        .build());
        prepareMedia(sourceUrl, position, playing);
        persistSubtitle(path, language(language), name);
    }

    private void searchSubtitles() {
        String[] languages = {
            "English",
            "Hindi",
            "Spanish",
            "French",
            "German",
            "Tamil",
            "Telugu",
            "Bengali",
            "Japanese",
            "Korean"
        };
        String[] codes = {"en", "hi", "es", "fr", "de", "ta", "te", "bn", "ja", "ko"};
        menu(
                "Subtitle language",
                languages,
                which -> {
                    toast("Searching subtitles…");
                    final String path = originalPath;
                    network.execute(
                            () -> {
                                try {
                                    JSONObject query = new JSONObject();
                                    put(query, "path", path);
                                    put(query, "language", codes[which]);
                                    put(query, "query", item.optString("title"));
                                    JSONArray rows =
                                            api.post(
                                                            "/api/files/playback/opensubtitles/search",
                                                            query)
                                                    .optJSONArray("results");
                                    main.post(
                                            () -> {
                                                if (destroyed) return;
                                                if (rows == null || rows.length() == 0) {
                                                    toast("No subtitles found.");
                                                    return;
                                                }
                                                String[] names = new String[rows.length()];
                                                for (int i = 0; i < names.length; i++)
                                                    names[i] =
                                                            (rows.optJSONObject(i)
                                                                                    .optBoolean(
                                                                                            "hash_match")
                                                                            ? "✓ "
                                                                            : "")
                                                                    + rows.optJSONObject(i)
                                                                            .optString(
                                                                                    "name",
                                                                                    "Subtitle");
                                                menu(
                                                        "Subtitles",
                                                        names,
                                                        selected -> {
                                                            JSONObject row =
                                                                    rows.optJSONObject(selected);
                                                            selectExternal(
                                                                    "os:" + row.optInt("id"),
                                                                    row.optString(
                                                                            "language",
                                                                            codes[which]),
                                                                    row.optString("name"));
                                                        });
                                            });
                                } catch (Exception failure) {
                                    main.post(
                                            () ->
                                                    toast(
                                                            "Subtitle search is unavailable. Check"
                                                                    + " the server's OpenSubtitles"
                                                                    + " connection."));
                                }
                            });
                });
    }

    private void showQuality() {
        if (versions.length() == 0) {
            toast("Original source is playing; no other versions are available.");
            return;
        }
        String[] labels = new String[versions.length()];
        for (int i = 0; i < labels.length; i++) {
            labels[i] = versions.optJSONObject(i).optString("quality", "original");
            if ("original".equalsIgnoreCase(labels[i])) labels[i] = "Original";
        }
        menu(
                "Quality",
                labels,
                which -> {
                    JSONObject version = versions.optJSONObject(which);
                    quality =
                            "original".equals(version.optString("quality"))
                                    ? "Original"
                                    : version.optString("quality");
                    currentPath = version.optString("path", originalPath);
                    prepareMedia(
                            version.has("url")
                                    ? api.absolute(version.optString("url"))
                                    : mediaUrl(currentPath),
                            player.getCurrentPosition(),
                            player.getPlayWhenReady());
                });
    }

    private void showSpeed() {
        float[] speeds = {.5f, .75f, 1f, 1.25f, 1.5f, 2f};
        String[] labels = {"0.5×", "0.75×", "Normal", "1.25×", "1.5×", "2×"};
        menu(
                "Playback speed",
                labels,
                which -> {
                    player.setPlaybackSpeed(speeds[which]);
                    syncDonor(true);
                });
    }

    private void showEpisodes() {
        if (!"series".equals(item.optString("kind")) || files.length() < 2) {
            toast("This title has no episode queue.");
            return;
        }
        String[] labels = new String[files.length()];
        for (int i = 0; i < labels.length; i++) {
            JSONObject file = files.optJSONObject(i);
            labels[i] =
                    (originalPath.equals(file.optString("path")) ? "✓ " : "")
                            + file.optString("display_name", file.optString("name"));
        }
        menu(
                "Episodes",
                labels,
                which -> {
                    String path = files.optJSONObject(which).optString("path");
                    loadPath(path, resumeFor(path));
                });
    }

    private void showInformation() {
        Format videoFormat = player.getVideoFormat(), audio = player.getAudioFormat();
        String info =
                "Source: "
                        + quality
                        + " · original bytes, native decoding\n"
                        + (videoFormat == null
                                ? "Video: waiting for metadata"
                                : "Video: "
                                        + videoFormat.width
                                        + " × "
                                        + videoFormat.height
                                        + " · "
                                        + videoFormat.sampleMimeType
                                        + "\nCodec string: "
                                        + safe(videoFormat.codecs)
                                        + "\nColor: "
                                        + (videoFormat.colorInfo == null
                                                ? "not reported"
                                                : videoFormat.colorInfo.toString()))
                        + "\nDecoder: "
                        + (decoder.isEmpty() ? "not reported" : decoder)
                        + "\n"
                        + (audio == null
                                ? "Audio: not reported"
                                : "Audio: "
                                        + audio.sampleMimeType
                                        + " · "
                                        + audio.channelCount
                                        + " channels · "
                                        + audio.sampleRate
                                        + " Hz")
                        + "\nSurface: SurfaceView\nFirst frame: "
                        + (firstFrame ? "rendered" : "not rendered")
                        + "\n"
                        + "HDR and surround output depend on the TV's decoder, source profile and"
                        + " audio output path.";
        new AlertDialog.Builder(this)
                .setTitle("Playback information")
                .setMessage(info)
                .setPositiveButton("Close", null)
                .show();
    }

    private void showSoundtrack() {
        if (remote) {
            toast("External soundtracks are available for your library files.");
            return;
        }
        menu(
                "External soundtrack",
                new String[] {
                    "Find an audio or video file",
                    "Audio delay −0.1 s",
                    "Audio delay +0.1 s",
                    "Audio clock −0.001×",
                    "Audio clock +0.001×",
                    "Use original audio",
                    "Soundtrack audio track",
                    "Match audio automatically",
                    "Stop automatic matching"
                },
                which -> {
                    if (which == 0) searchSoundtrack();
                    else if (which == 6) showDonorTracks();
                    else if (which == 7) alignSoundtrack();
                    else if (which == 8) {
                        if (alignmentCancelled != null) alignmentCancelled.set(true);
                    } else if (which == 5) {
                        stopDonor();
                        persistDonor(new JSONObject());
                    } else if (donorSelection == null) toast("Choose a soundtrack first.");
                    else {
                        double delay = donorSelection.optDouble("delay"),
                                rate = donorSelection.optDouble("rate", 1);
                        if (which == 1) delay -= .1;
                        if (which == 2) delay += .1;
                        if (which == 3) rate -= .001;
                        if (which == 4) rate += .001;
                        put(donorSelection, "delay", delay);
                        put(donorSelection, "rate", Math.max(.5, Math.min(2, rate)));
                        syncDonor(true);
                        persistDonor(donorSelection);
                        toast(
                                String.format(
                                        Locale.ROOT,
                                        "Soundtrack delay %.1f s · rate %.3f×",
                                        delay,
                                        rate));
                    }
                });
    }

    private void searchSoundtrack() {
        EditText query = new EditText(this);
        query.setSingleLine(true);
        query.setText(item.optString("title"));
        query.setImeOptions(
                android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH
                        | android.view.inputmethod.EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        AlertDialog dialog =
                new AlertDialog.Builder(this)
                        .setTitle("Find a soundtrack")
                        .setView(query)
                        .setPositiveButton(
                                "Search",
                                (d, w) -> loadSoundtrackResults(query.getText().toString()))
                        .setNegativeButton("Cancel", null)
                        .create();
        dialog.show();
        query.setOnEditorActionListener(
                (v, action, event) -> {
                    if (action == android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH) {
                        dialog.dismiss();
                        loadSoundtrackResults(query.getText().toString());
                        return true;
                    }
                    return false;
                });
    }

    private void loadSoundtrackResults(String query) {
        toast("Finding soundtracks…");
        network.execute(
                () -> {
                    try {
                        JSONArray found =
                                api.get(
                                                "/api/files/search?q="
                                                        + encoded(query)
                                                        + "&item_type=file&limit=30")
                                        .optJSONArray("data");
                        List<JSONObject> rows = new ArrayList<>();
                        if (found != null)
                            for (int i = 0; i < found.length(); i++) {
                                JSONObject row = found.optJSONObject(i);
                                String path = row.optString("relative_path");
                                if (!path.equals(originalPath)
                                        && path.toLowerCase(Locale.ROOT)
                                                .matches(
                                                        ".*\\.(mkv|mp4|webm|mov|avi|m4v|ts|m2ts|mp3|aac|m4a|wav|flac|ogg)$"))
                                    rows.add(row);
                            }
                        main.post(
                                () -> {
                                    if (destroyed) return;
                                    if (rows.isEmpty()) {
                                        toast("No matching soundtrack files found.");
                                        return;
                                    }
                                    String[] labels = new String[rows.size()];
                                    for (int i = 0; i < labels.length; i++)
                                        labels[i] =
                                                rows.get(i)
                                                        .optString(
                                                                "name",
                                                                rows.get(i)
                                                                        .optString(
                                                                                "relative_path"));
                                    menu(
                                            "Choose soundtrack",
                                            labels,
                                            which -> {
                                                JSONObject choice = new JSONObject();
                                                put(
                                                        choice,
                                                        "donor",
                                                        rows.get(which).optString("relative_path"));
                                                put(choice, "track_id", 0);
                                                put(choice, "delay", 0);
                                                put(choice, "rate", 1);
                                                openDonor(choice);
                                                persistDonor(choice);
                                            });
                                });
                    } catch (Exception failure) {
                        main.post(() -> toast("Unable to search soundtrack files."));
                    }
                });
    }

    private void openDonor(JSONObject selection) {
        stopDonor();
        donorSelection = selection;
        donor =
                new ExoPlayer.Builder(this, audioRoute.renderers(this))
                        .setMediaSourceFactory(
                                new DefaultMediaSourceFactory(
                                        () -> new NativePlayerDataSource(api)))
                        .build();
        donor.setVolume(volume);
        donor.setTrackSelectionParameters(
                donor.getTrackSelectionParameters()
                        .buildUpon()
                        .setTrackTypeDisabled(C.TRACK_TYPE_VIDEO, true)
                        .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, true)
                        .build());
        donor.setMediaItem(MediaItem.fromUri(mediaUrl(selection.optString("donor"))));
        donor.prepare();
        player.setVolume(0);
        donor.addListener(
                new Player.Listener() {
                    @Override
                    public void onPlayerError(PlaybackException error) {
                        toast("This soundtrack cannot be decoded. Original audio restored.");
                        stopDonor();
                    }

                    @Override
                    public void onTracksChanged(Tracks tracks) {
                        if (donor == null || donorSelection == null) return;
                        int wanted = donorSelection.optInt("track_id"), ordinal = 0;
                        boolean nativeOnly = donorSelection.optBoolean("native_track_only");
                        for (Tracks.Group group : tracks.getGroups()) {
                            if (group.getType() != C.TRACK_TYPE_AUDIO) continue;
                            for (int i = 0; i < group.length; i++, ordinal++) {
                                Integer containerId =
                                        NativePlayerTrackIds.containerId(
                                                group.getTrackFormat(i).id);
                                boolean matches =
                                        nativeOnly
                                                ? ordinal
                                                        == donorSelection.optInt(
                                                                "native_track_ordinal")
                                                : wanted == 0
                                                        ? ordinal == 0
                                                        : containerId != null
                                                                && containerId == wanted;
                                if (!matches || group.isTrackSelected(i)) continue;
                                donor.setTrackSelectionParameters(
                                        donor.getTrackSelectionParameters()
                                                .buildUpon()
                                                .setOverrideForType(
                                                        new TrackSelectionOverride(
                                                                group.getMediaTrackGroup(), i))
                                                .build());
                                return;
                            }
                        }
                    }
                });
        syncDonor(true);
    }

    private void syncDonor(boolean force) {
        if (donor == null || donorSelection == null) return;
        long now = SystemClock.elapsedRealtime();
        if (!force && now - lastDonorSync < 1000) return;
        lastDonorSync = now;
        double delay = donorSelection.optDouble("delay"),
                rate = donorSelection.optDouble("rate", 1);
        long expected =
                Math.max(0, (long) ((player.getCurrentPosition() / 1000d - delay) * rate * 1000));
        if (force || Math.abs(donor.getCurrentPosition() - expected) > 200) donor.seekTo(expected);
        donor.setPlaybackSpeed((float) (player.getPlaybackParameters().speed * rate));
        donor.setPlayWhenReady(player.isPlaying() && player.getCurrentPosition() / 1000d >= delay);
    }

    private void stopDonor() {
        if (alignmentCancelled != null) alignmentCancelled.set(true);
        if (donor != null) {
            donor.release();
            donor = null;
        }
        donorSelection = null;
        if (player != null) player.setVolume(volume);
    }

    private JSONObject preferredSoundtrack(JSONObject shared) {
        String saved =
                getSharedPreferences("native-player", MODE_PRIVATE)
                        .getString("soundtrack:" + localBookmarkKey(originalPath), "");
        if (!saved.isEmpty())
            try {
                JSONObject local = new JSONObject(saved);
                if (local.optBoolean("native_track_only")
                        && local.optString("donor").equals(shared.optString("donor"))) return local;
            } catch (JSONException ignored) {
            }
        return shared;
    }

    private void persistDonor(JSONObject value) {
        getSharedPreferences("native-player", MODE_PRIVATE)
                .edit()
                .putString("soundtrack:" + localBookmarkKey(originalPath), value.toString())
                .apply();
        if (value.optBoolean("native_track_only")) return;
        JSONObject choice = new JSONObject();
        put(choice, "path", originalPath);
        put(choice, "donor", value.optString("donor"));
        put(choice, "track_id", value.optInt("track_id"));
        put(choice, "delay", value.optDouble("delay"));
        put(choice, "rate", value.optDouble("rate", 1));
        network.execute(
                () -> {
                    try {
                        api.put("/api/files/playback/alternate-audio", choice);
                    } catch (Exception ignored) {
                    }
                });
    }

    private void menu(String heading, String[] labels, java.util.function.IntConsumer action) {
        menu(heading, labels, action, 0);
    }

    private void menu(
            String heading,
            String[] labels,
            java.util.function.IntConsumer action,
            int selectedRow) {
        if (destroyed) return;
        main.removeCallbacks(hideControls);
        Runnable parent = nextMenuParent;
        nextMenuParent = null;
        menuDialog =
                NativePlayerMenu.show(
                        this,
                        heading,
                        labels,
                        which -> {
                            nextMenuParent =
                                    () -> {
                                        nextMenuParent = parent;
                                        menu(heading, labels, action, which);
                                    };
                            action.accept(which);
                        },
                        this::scheduleHide,
                        parent,
                        selectedRow);
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (player == null) return super.dispatchKeyEvent(event);
        int key = event.getKeyCode();
        if (key == KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == KeyEvent.ACTION_UP) {
                if (controls) setControls(false);
                else finish();
            }
            return true;
        }
        if (event.getAction() == KeyEvent.ACTION_DOWN) {
            main.removeCallbacks(hideControls);
            switch (key) {
                case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
                    togglePlay();
                    return true;
                case KeyEvent.KEYCODE_MEDIA_PLAY:
                    player.play();
                    return true;
                case KeyEvent.KEYCODE_MEDIA_PAUSE:
                    player.pause();
                    return true;
                case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
                    seek(10000);
                    return true;
                case KeyEvent.KEYCODE_MEDIA_REWIND:
                    seek(-10000);
                    return true;
                case KeyEvent.KEYCODE_MEDIA_NEXT:
                    nextEpisode(1);
                    return true;
                case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                    nextEpisode(-1);
                    return true;
                case KeyEvent.KEYCODE_MENU:
                    setControls(true);
                    showSettings();
                    return true;
                default:
                    break;
            }
            if (!controls
                    && (key == KeyEvent.KEYCODE_DPAD_CENTER
                            || key == KeyEvent.KEYCODE_ENTER
                            || key == KeyEvent.KEYCODE_DPAD_UP
                            || key == KeyEvent.KEYCODE_DPAD_DOWN
                            || key == KeyEvent.KEYCODE_DPAD_LEFT
                            || key == KeyEvent.KEYCODE_DPAD_RIGHT)) {
                setControls(true);
                if (key == KeyEvent.KEYCODE_DPAD_LEFT || key == KeyEvent.KEYCODE_DPAD_RIGHT) {
                    timeline.requestFocus();
                    seek(key == KeyEvent.KEYCODE_DPAD_RIGHT ? 10000 : -10000);
                } else play.requestFocus();
                return true;
            }
        }
        if (event.getAction() == KeyEvent.ACTION_UP) scheduleHide();
        return super.dispatchKeyEvent(event);
    }

    @Override
    protected void onResume() {
        super.onResume();
        resumed = true;
        immersive();
        main.removeCallbacks(tick);
        main.post(tick);
    }

    @Override
    protected void onPause() {
        resumed = false;
        main.removeCallbacks(tick);
        main.removeCallbacks(hideControls);
        saveProgress(true);
        if (player != null) player.pause();
        if (donor != null) donor.pause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        destroyed = true;
        main.removeCallbacksAndMessages(null);
        if (preview != null) preview.close();
        stopDonor();
        if (video != null) video.setPlayer(null);
        if (player != null) {
            player.release();
            player = null;
        }
        network.shutdown();
        super.onDestroy();
    }

    private void immersive() {
        getWindow().getDecorView();
        getWindow().getInsetsController().hide(WindowInsets.Type.systemBars());
        getWindow()
                .getInsetsController()
                .setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }

    private void toast(String value) {
        if (!destroyed) Toast.makeText(this, value, Toast.LENGTH_SHORT).show();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static String encoded(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8);
    }

    private static String safe(String value) {
        return value == null ? "not reported" : value;
    }

    private static String language(String value) {
        return value != null && value.matches("[a-z]{2,3}") ? value : "en";
    }

    private static String trackName(Format format, int index) {
        String language =
                format.language == null || "und".equals(format.language)
                        ? "Track " + (index + 1)
                        : Locale.forLanguageTag(format.language).getDisplayLanguage();
        return (format.label == null ? language : format.label)
                + (format.sampleMimeType == null || !format.sampleMimeType.startsWith("audio/")
                        ? ""
                        : " · "
                                + format.sampleMimeType
                                        .replace("audio/", "")
                                        .replace("application/", ""))
                + (format.channelCount > 0 ? " · " + format.channelCount + "ch" : "");
    }

    private static String clock(long milliseconds) {
        long seconds = Math.max(0, milliseconds / 1000);
        return seconds >= 3600
                ? String.format(
                        Locale.ROOT,
                        "%d:%02d:%02d",
                        seconds / 3600,
                        seconds / 60 % 60,
                        seconds % 60)
                : String.format(Locale.ROOT, "%d:%02d", seconds / 60, seconds % 60);
    }

    private static String bookmarkKey(String path) {
        try {
            byte[] value =
                    MessageDigest.getInstance("SHA-256")
                            .digest(path.getBytes(StandardCharsets.UTF_8));
            StringBuilder key = new StringBuilder("resume:");
            for (byte b : value) key.append(String.format(Locale.ROOT, "%02x", b));
            return key.toString();
        } catch (Exception ignored) {
            return "resume:" + path.hashCode();
        }
    }

    private String localBookmarkKey(String path) {
        String identity = path;
        if (path != null && path.contains("/online/media/"))
            identity =
                    "online:"
                            + item.optString("imdb_id", item.optString("id"))
                            + ":"
                            + item.optInt("season")
                            + ":"
                            + item.optInt("episode");
        return bookmarkKey(api.getProfile() + "\u0000" + identity);
    }

    private void showSources() {
        String id = item.optString("imdb_id");
        if (id.isEmpty()) {
            toast("Online sources need a title identity from the catalogue.");
            return;
        }
        toast("Finding sources…");
        JSONObject episode = currentFile();
        int season = episode == null ? item.optInt("season") : episode.optInt("season");
        int number = episode == null ? item.optInt("episode") : episode.optInt("episode");
        String query =
                "/api/files/online/sources?imdb_id="
                        + encoded(id)
                        + "&kind="
                        + encoded(item.optString("kind", "movie"))
                        + "&season="
                        + season
                        + "&episode="
                        + number;
        network.execute(
                () -> {
                    try {
                        JSONArray entries = api.get(query).optJSONArray("sources");
                        main.post(
                                () -> {
                                    if (destroyed) return;
                                    List<String> labels = new ArrayList<>();
                                    List<String> paths = new ArrayList<>();
                                    if (item.optBoolean("owned")
                                            && !item.optString("path").isEmpty()) {
                                        labels.add("Your library · original");
                                        paths.add(
                                                item.optString(
                                                        "resume_path", item.optString("path")));
                                    }
                                    if (entries != null)
                                        for (int i = 0; i < entries.length(); i++) {
                                            JSONObject source = entries.optJSONObject(i);
                                            if (source == null || source.optString("url").isEmpty())
                                                continue;
                                            labels.add(
                                                    source.optString("provider", "Online")
                                                            + " · "
                                                            + source.optString(
                                                                    "label",
                                                                    source.optString(
                                                                            "quality",
                                                                            "Original")));
                                            paths.add(source.optString("url"));
                                        }
                                    if (labels.isEmpty()) {
                                        toast("No alternative source is available.");
                                        return;
                                    }
                                    menu(
                                            "Sources",
                                            labels.toArray(new String[0]),
                                            which ->
                                                    loadPath(
                                                            paths.get(which),
                                                            player.getCurrentPosition()));
                                });
                    } catch (Exception unavailable) {
                        main.post(() -> toast("Unable to retrieve sources right now."));
                    }
                });
    }

    private void showDonorTracks() {
        if (donor == null) {
            toast("Choose a soundtrack first.");
            return;
        }
        List<String> labels = new ArrayList<>();
        List<Runnable> choices = new ArrayList<>();
        int ordinal = 0;
        for (Tracks.Group group : donor.getCurrentTracks().getGroups()) {
            if (group.getType() != C.TRACK_TYPE_AUDIO) continue;
            for (int i = 0; i < group.length; i++, ordinal++) {
                final int track = i, value = ordinal;
                labels.add(
                        (group.isTrackSelected(i) ? "✓ " : "")
                                + trackName(group.getTrackFormat(i), i));
                choices.add(
                        () -> {
                            if (donor == null || donorSelection == null) return;
                            Integer container =
                                    NativePlayerTrackIds.containerId(
                                            group.getTrackFormat(track).id);
                            put(donorSelection, "native_track_ordinal", value);
                            put(donorSelection, "native_track_only", container == null);
                            if (container != null) put(donorSelection, "track_id", container);
                            donor.setTrackSelectionParameters(
                                    donor.getTrackSelectionParameters()
                                            .buildUpon()
                                            .setOverrideForType(
                                                    new TrackSelectionOverride(
                                                            group.getMediaTrackGroup(), track))
                                            .build());
                            persistDonor(donorSelection);
                        });
            }
        }
        if (labels.isEmpty()) {
            toast("The soundtrack metadata is still loading.");
            return;
        }
        menu("Soundtrack audio", labels.toArray(new String[0]), which -> choices.get(which).run());
    }

    private void alignSoundtrack() {
        if (donor == null || donorSelection == null || !validDuration()) {
            toast("Choose a soundtrack first.");
            return;
        }
        if (alignmentCancelled != null) alignmentCancelled.set(true);
        AtomicBoolean cancelled = new AtomicBoolean();
        alignmentCancelled = cancelled;
        final JSONObject selection = donorSelection;
        String reference = sourceUrl, alternative = mediaUrl(selection.optString("donor"));
        int track = selectedAudioOrdinal(donor), referenceTrack = selectedAudioOrdinal();
        double duration =
                Math.min(
                                player.getDuration(),
                                donor.getDuration() > 0
                                        ? donor.getDuration()
                                        : player.getDuration())
                        / 1000d;
        toast("Matching two short audio samples on the TV…");
        network.execute(
                () -> {
                    try {
                        double[] result =
                                NativeAudioAlignment.align(
                                        api,
                                        reference,
                                        alternative,
                                        referenceTrack,
                                        track,
                                        duration,
                                        cancelled);
                        main.post(
                                () -> {
                                    if (destroyed || cancelled.get() || donorSelection != selection)
                                        return;
                                    put(selection, "delay", result[0]);
                                    put(selection, "rate", result[1]);
                                    syncDonor(true);
                                    persistDonor(selection);
                                    toast(
                                            String.format(
                                                    Locale.ROOT,
                                                    "Audio matched · delay %.2f s · rate %.5f×",
                                                    result[0],
                                                    result[1]));
                                });
                    } catch (Exception failure) {
                        main.post(
                                () -> {
                                    if (!destroyed && !cancelled.get())
                                        toast(
                                                failure.getMessage() == null
                                                        ? "Automatic alignment unavailable. Manual"
                                                                + " sync is available."
                                                        : failure.getMessage());
                                });
                    }
                });
    }

    private int selectedAudioOrdinal() {
        return selectedAudioOrdinal(player);
    }

    private int selectedAudioOrdinal(ExoPlayer source) {
        int ordinal = 0;
        for (Tracks.Group group : source.getCurrentTracks().getGroups())
            if (group.getType() == C.TRACK_TYPE_AUDIO)
                for (int i = 0; i < group.length; i++, ordinal++)
                    if (group.isTrackSelected(i)) return ordinal;
        return 0;
    }

    private static void put(JSONObject object, String key, Object value) {
        try {
            object.put(key, value);
        } catch (JSONException invalid) {
            throw new IllegalArgumentException(invalid);
        }
    }
}
