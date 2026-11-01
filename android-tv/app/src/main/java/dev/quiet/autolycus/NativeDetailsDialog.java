package dev.quiet.autolycus;

import android.app.Dialog;
import android.content.Context;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Scrollable title details whose description is a deliberate D-pad reading stop. */
public final class NativeDetailsDialog extends Dialog {
    public interface Listener {
        void onPlay(JSONObject item, String path);

        void onOnline(JSONObject item);

        void onTrailer(JSONObject item);
    }

    private final Listener listener;
    private final NativeArtwork artwork;
    private JSONObject item;
    private final ScrollView scroll;
    private final LinearLayout stack;
    private final ImageView backdrop;
    private final TextView title;
    private final TextView metadata;
    private final TextView overview;
    private final TextView credits;
    private final TextView genres;
    private final TextView primary;
    private final TextView trailer;
    private final LinearLayout episodes;
    private final List<View> actions = new ArrayList<>();
    private final List<View> episodeButtons = new ArrayList<>();
    private final TextView episodeHeading;

    public NativeDetailsDialog(
            Context context, AutolycusApi api, JSONObject item, Listener listener) {
        super(context);
        this.listener = listener;
        this.item = item;
        artwork = new NativeArtwork(api);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        FrameLayout panel = new FrameLayout(context);
        panel.setBackground(NativeHomeView.surface(NativeHomeView.BACKGROUND, dp(12)));
        panel.setClipToOutline(true);
        scroll =
                new ScrollView(context) {
                    @Override
                    protected int computeScrollDeltaToGetChildRectOnScreen(Rect rect) {
                        return 0;
                    }
                };
        scroll.setVerticalScrollBarEnabled(false);
        scroll.setOverScrollMode(View.OVER_SCROLL_NEVER);
        scroll.setFocusable(false);
        scroll.setFillViewport(false);
        scroll.setClipChildren(false);
        scroll.setClipToPadding(false);
        panel.addView(scroll, new FrameLayout.LayoutParams(-1, -1));
        stack = new LinearLayout(context);
        stack.setOrientation(LinearLayout.VERTICAL);
        stack.setClipChildren(false);
        stack.setClipToPadding(false);
        scroll.addView(stack, new ScrollView.LayoutParams(-1, -2));

        FrameLayout banner = new FrameLayout(context);
        banner.setBackgroundColor(0xff171b22);
        stack.addView(banner, new LinearLayout.LayoutParams(-1, dp(206)));
        backdrop = new ImageView(context);
        backdrop.setScaleType(ImageView.ScaleType.CENTER_CROP);
        banner.addView(backdrop, new FrameLayout.LayoutParams(-1, -1));
        View shade = new View(context);
        shade.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.BOTTOM_TOP,
                        new int[] {0xff101113, 0xb0101113, 0x00101113}));
        banner.addView(shade, new FrameLayout.LayoutParams(-1, -1));
        title = NativeHomeView.label(context, "", 32, NativeHomeView.WHITE, true);
        title.setMaxLines(2);
        FrameLayout.LayoutParams titleBounds = new FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM);
        titleBounds.setMargins(dp(24), 0, dp(24), dp(18));
        banner.addView(title, titleBounds);

        LinearLayout body = new LinearLayout(context);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setClipChildren(false);
        body.setClipToPadding(false);
        body.setPadding(dp(24), 0, dp(24), dp(28));
        stack.addView(body, new LinearLayout.LayoutParams(-1, -2));
        metadata = NativeHomeView.label(context, "", 12, 0xffb3bbc7, false);
        body.addView(metadata);
        LinearLayout buttons = new LinearLayout(context);
        buttons.setGravity(Gravity.CENTER_VERTICAL);
        buttons.setClipChildren(false);
        buttons.setClipToPadding(false);
        LinearLayout.LayoutParams buttonRow = new LinearLayout.LayoutParams(-1, dp(66));
        buttonRow.topMargin = dp(6);
        body.addView(buttons, buttonRow);
        primary = NativeHomeView.action(context, "Play", true);
        primary.setOnClickListener(
                v -> {
                    JSONObject selected = this.item;
                    dismiss();
                    if (selected.optBoolean("owned"))
                        listener.onPlay(selected, NativeHomeView.playPath(selected));
                    else listener.onOnline(selected);
                });
        buttons.addView(primary, new LinearLayout.LayoutParams(-2, dp(44)));
        actions.add(primary);
        trailer = NativeHomeView.action(context, "Trailer", false);
        trailer.setBackground(NativeHomeView.surface(0xff262a31, dp(6)));
        trailer.setOnClickListener(v -> listener.onTrailer(this.item));
        LinearLayout.LayoutParams trailerBounds = new LinearLayout.LayoutParams(-2, dp(44));
        trailerBounds.leftMargin = dp(12);
        buttons.addView(trailer, trailerBounds);
        actions.add(trailer);

        overview = NativeHomeView.label(context, "", 15, 0xffc7cbd3, false);
        overview.setLineSpacing(dp(5), 1f);
        overview.setFocusable(true);
        overview.setDefaultFocusHighlightEnabled(false);
        overview.setContentDescription("Movie description. Press Down to read more.");
        overview.setOnFocusChangeListener(
                (v, focused) -> overview.setTextColor(focused ? NativeHomeView.WHITE : 0xffc7cbd3));
        LinearLayout.LayoutParams overviewBounds = new LinearLayout.LayoutParams(-1, -2);
        overviewBounds.topMargin = dp(8);
        overviewBounds.bottomMargin = dp(16);
        body.addView(overview, overviewBounds);
        genres = NativeHomeView.label(context, "", 12, 0xff9facbf, false);
        LinearLayout.LayoutParams genresBounds = new LinearLayout.LayoutParams(-1, -2);
        genresBounds.bottomMargin = dp(12);
        body.addView(genres, genresBounds);
        credits = NativeHomeView.label(context, "", 13, 0xff9ba3af, false);
        credits.setLineSpacing(dp(5), 1f);
        body.addView(credits);
        episodeHeading = NativeHomeView.label(context, "Episodes", 20, NativeHomeView.WHITE, true);
        LinearLayout.LayoutParams headingBounds = new LinearLayout.LayoutParams(-1, -2);
        headingBounds.topMargin = dp(26);
        headingBounds.bottomMargin = dp(12);
        body.addView(episodeHeading, headingBounds);
        episodes = new LinearLayout(context);
        episodes.setOrientation(LinearLayout.VERTICAL);
        body.addView(episodes);
        setContentView(panel);
        Window window = getWindow();
        window.setBackgroundDrawableResource(android.R.color.transparent);
        window.setDimAmount(.78f);
        window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
        int screenWidth = context.getResources().getDisplayMetrics().widthPixels;
        int screenHeight = context.getResources().getDisplayMetrics().heightPixels;
        window.setLayout(Math.min(dp(800), screenWidth - dp(80)), screenHeight - dp(48));
        window.setGravity(Gravity.CENTER);
        update(item);
        setOnShowListener(ignored -> primary.requestFocus());
    }

    public void update(JSONObject enriched) {
        if (enriched == null) return;
        String previousId = item == null ? "" : item.optString("id");
        this.item = enriched;
        title.setText(item.optString("title", ""));
        metadata.setText(
                NativeHomeView.metadata(item)
                        + (item.optString("resolution", "").isEmpty()
                                ? ""
                                : "   ·   " + item.optString("resolution")));
        overview.setText(
                item.optString("overview", "").isEmpty()
                        ? "A synopsis is not available for this title."
                        : item.optString("overview"));
        genres.setText(join(item.optJSONArray("genres"), "  ·  ", 8));
        genres.setVisibility(genres.length() == 0 ? View.GONE : View.VISIBLE);
        String cast = join(item.optJSONArray("cast"), ", ", 8);
        String directors = join(item.optJSONArray("directors"), ", ", 5);
        StringBuilder details = new StringBuilder();
        if (!cast.isEmpty()) details.append("Cast    ").append(cast);
        if (!directors.isEmpty())
            details.append(details.length() == 0 ? "" : "\n")
                    .append("Director    ")
                    .append(directors);
        String awards = item.optString("awards", "");
        if (!awards.isEmpty()) details.append(details.length() == 0 ? "" : "\n").append(awards);
        credits.setText(details.toString());
        credits.setVisibility(details.length() == 0 ? View.GONE : View.VISIBLE);
        primary.setText(
                item.optBoolean("owned")
                        ? "▶  "
                                + (item.optBoolean("next_episode")
                                        ? "Next episode"
                                        : item.optJSONObject("progress") != null
                                                ? "Continue watching"
                                                : "Play")
                        : "Watch options");
        JSONArray trailers = item.optJSONArray("trailers");
        trailer.setVisibility(trailers != null && trailers.length() > 0 ? View.VISIBLE : View.GONE);
        String background = item.optString("background", "");
        if (background.isEmpty() || "null".equals(background))
            background = item.optString("poster", "");
        artwork.load(backdrop, background, 1600, 700);
        JSONArray files = item.optJSONArray("files");
        boolean hasEpisodes =
                item.optBoolean("owned")
                        && "series".equals(item.optString("kind"))
                        && files != null
                        && files.length() > 0;
        episodeHeading.setVisibility(hasEpisodes ? View.VISIBLE : View.GONE);
        episodes.setVisibility(hasEpisodes ? View.VISIBLE : View.GONE);
        if (hasEpisodes && (episodeButtons.isEmpty() || !previousId.equals(item.optString("id"))))
            buildEpisodes(files);
    }

    private void buildEpisodes(JSONArray files) {
        episodes.removeAllViews();
        episodeButtons.clear();
        int previousSeason = -1;
        for (int i = 0; i < Math.min(files.length(), 500); i++) {
            JSONObject file = files.optJSONObject(i);
            if (file == null) continue;
            int season = file.optInt("season", 0);
            if (season != previousSeason) {
                TextView heading =
                        NativeHomeView.label(
                                getContext(),
                                "Season " + Math.max(1, season),
                                13,
                                0xffa7b0c0,
                                true);
                heading.setPadding(0, dp(12), 0, dp(10));
                episodes.addView(heading);
                previousSeason = season;
            }
            String name =
                    file.optString(
                            "display_name",
                            file.optString("name", "Episode " + file.optInt("episode")));
            TextView button =
                    NativeHomeView.action(
                            getContext(),
                            String.format(
                                            java.util.Locale.ROOT,
                                            "%02d   ",
                                            file.optInt("episode", i + 1))
                                    + name,
                            false);
            button.setTextSize(14);
            button.setGravity(Gravity.CENTER_VERTICAL | Gravity.LEFT);
            button.setMaxLines(2);
            button.setPadding(dp(14), dp(10), dp(14), dp(10));
            button.setContentDescription("Play " + name);
            button.setOnClickListener(
                    v -> {
                        JSONObject selected = this.item;
                        dismiss();
                        listener.onPlay(selected, file.optString("path"));
                    });
            LinearLayout.LayoutParams bounds = new LinearLayout.LayoutParams(-1, dp(56));
            bounds.bottomMargin = dp(4);
            episodes.addView(button, bounds);
            episodeButtons.add(button);
        }
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        int key = event.getKeyCode();
        if (key == KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == KeyEvent.ACTION_UP) dismiss();
            return true;
        }
        if (event.getAction() != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event);
        View focused = getCurrentFocus();
        if (key == KeyEvent.KEYCODE_DPAD_DOWN) {
            if (actions.contains(focused)) {
                overview.requestFocus();
                scroll.smoothScrollTo(0, Math.max(0, relativeTop(overview) - dp(22)));
            } else if (focused == overview || focused == null) {
                int episodeTop =
                        episodeButtons.isEmpty()
                                ? stack.getHeight()
                                : relativeTop(episodeButtons.get(0));
                int visibleBottom = scroll.getScrollY() + scroll.getHeight() - dp(24);
                if (!episodeButtons.isEmpty() && visibleBottom >= episodeTop + dp(30)) {
                    episodeButtons.get(0).requestFocus();
                    reveal(episodeButtons.get(0));
                } else scroll.smoothScrollBy(0, dp(105));
            } else {
                int index = episodeButtons.indexOf(focused);
                if (index >= 0 && index + 1 < episodeButtons.size()) {
                    episodeButtons.get(index + 1).requestFocus();
                    reveal(episodeButtons.get(index + 1));
                } else scroll.smoothScrollBy(0, dp(80));
            }
            return true;
        }
        if (key == KeyEvent.KEYCODE_DPAD_UP) {
            int index = episodeButtons.indexOf(focused);
            if (index > 0) {
                episodeButtons.get(index - 1).requestFocus();
                reveal(episodeButtons.get(index - 1));
            } else if (index == 0) {
                overview.requestFocus();
                scroll.smoothScrollTo(0, Math.max(0, relativeTop(overview) - dp(22)));
            } else if (focused == overview
                    && scroll.getScrollY() > relativeTop(overview) - dp(22)) {
                scroll.smoothScrollBy(0, -dp(105));
            } else if (focused == overview) {
                primary.requestFocus();
                reveal(primary);
            } else {
                scroll.smoothScrollTo(0, 0);
            }
            return true;
        }
        if ((key == KeyEvent.KEYCODE_DPAD_LEFT || key == KeyEvent.KEYCODE_DPAD_RIGHT)
                && actions.contains(focused)) {
            int index = actions.indexOf(focused);
            int step = key == KeyEvent.KEYCODE_DPAD_RIGHT ? 1 : -1;
            for (int next = index + step; next >= 0 && next < actions.size(); next += step) {
                if (actions.get(next).getVisibility() == View.VISIBLE) {
                    actions.get(next).requestFocus();
                    break;
                }
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
    }

    private void reveal(View view) {
        int top = relativeTop(view);
        if (top < scroll.getScrollY() + dp(16)) scroll.smoothScrollTo(0, Math.max(0, top - dp(16)));
        else if (top + view.getHeight() > scroll.getScrollY() + scroll.getHeight() - dp(20))
            scroll.smoothScrollTo(0, top + view.getHeight() - scroll.getHeight() + dp(20));
    }

    private int relativeTop(View view) {
        int top = view.getTop();
        android.view.ViewParent parent = view.getParent();
        while (parent instanceof View && parent != stack) {
            top += ((View) parent).getTop();
            parent = parent.getParent();
        }
        return top;
    }

    private int dp(float value) {
        return NativeHomeView.dp(getContext(), value);
    }

    private static String join(JSONArray values, String separator, int maximum) {
        if (values == null) return "";
        List<String> text = new ArrayList<>();
        for (int i = 0; i < Math.min(values.length(), maximum); i++) {
            Object value = values.opt(i);
            if (value instanceof JSONObject) text.add(((JSONObject) value).optString("name", ""));
            else if (value != null && value != JSONObject.NULL) text.add(value.toString());
        }
        return android.text.TextUtils.join(separator, text);
    }
}
