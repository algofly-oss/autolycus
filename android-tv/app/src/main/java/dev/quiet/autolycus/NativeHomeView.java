package dev.quiet.autolycus;

import android.animation.ValueAnimator;
import android.app.Dialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.ColorFilter;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewTreeObserver;
import android.view.Window;
import android.view.WindowManager;
import android.view.animation.DecelerateInterpolator;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/** Native cinema homepage. Focus belongs to rows and primary movie actions. */
public final class NativeHomeView extends FrameLayout {
    public interface Listener {
        void onDetails(JSONObject item);

        void onPlay(JSONObject item, String path);

        void onSearch(String query);

        void onProfiles();

        void onSettings();
    }

    static final int BACKGROUND = 0xff101113;
    static final int WHITE = 0xfff4f4f5;
    static final int MUTED = 0xff969ba5;
    private final Listener listener;
    private final NativeArtwork artwork;
    private final LinearLayout header;
    private boolean scrolledHeader;
    private final LinearLayout content;
    private final ScrollView scroll;
    private final List<List<View>> rows = new ArrayList<>();
    private final List<View> sections = new ArrayList<>();
    private final List<HorizontalScrollView> rails = new ArrayList<>();
    private final List<JSONObject> library = new ArrayList<>();
    private final List<JSONObject> shelves = new ArrayList<>();
    private final List<TextView> categoryButtons = new ArrayList<>();
    private final List<PosterCard> posters = new ArrayList<>();
    private boolean refreshPosted;
    private final Runnable refreshPosters =
            () -> {
                refreshPosted = false;
                int[] position = new int[2];
                Rect visible = new Rect();
                int height = getResources().getDisplayMetrics().heightPixels;
                for (PosterCard card : posters) {
                    if (card.getGlobalVisibleRect(visible)) card.requestArtwork();
                    else {
                        card.getLocationInWindow(position);
                        if (position[1] < -height || position[1] > height * 2)
                            card.releaseArtwork();
                    }
                }
            };
    private JSONObject catalog = new JSONObject();
    private String category = "all";
    private String lastMovie = "";
    private int preferredColumn;
    private int savedFocusRow = 1;
    private int savedFocusColumn;
    private ValueAnimator verticalScroll;
    private ViewTreeObserver.OnGlobalLayoutListener pendingFocusRestore;
    private boolean searchResults;
    private String searchQuery = "";
    private JSONArray searchItems = new JSONArray();
    private TextView profile;
    private View initialFocus;
    private Dialog searchDialog;
    private final FrameLayout searchLoading;
    private final SharedPreferences navigationDebug;
    private final Runnable recordSettledFocus = () -> recordNavigationFocus(findFocus());
    private final ViewTreeObserver.OnGlobalFocusChangeListener navigationObserver =
            (previous, focused) -> {
                recordNavigationFocus(focused);
                removeCallbacks(recordSettledFocus);
                postDelayed(recordSettledFocus, 350);
            };

    public NativeHomeView(Context context, AutolycusApi api, Listener listener) {
        super(context);
        this.listener = listener;
        navigationDebug =
                BuildConfig.DEBUG
                        ? context.getSharedPreferences("native-navigation", Context.MODE_PRIVATE)
                        : null;
        artwork = new NativeArtwork(api);
        setBackgroundColor(BACKGROUND);
        setClipChildren(false);
        scroll =
                new ScrollView(context) {
                    @Override
                    protected int computeScrollDeltaToGetChildRectOnScreen(Rect rect) {
                        return 0;
                    }
                };
        scroll.setFillViewport(false);
        scroll.setFocusable(false);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.setOverScrollMode(OVER_SCROLL_NEVER);
        scroll.setClipChildren(false);
        scroll.setOnScrollChangeListener(
                (View.OnScrollChangeListener)
                        (view, x, y, oldX, oldY) -> {
                            refreshArtworkSoon();
                            updateHeaderTint();
                        });
        content = new LinearLayout(context);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setClipChildren(false);
        content.setPadding(0, 0, 0, dp(context, 40));
        scroll.addView(content, new ScrollView.LayoutParams(-1, -2));
        FrameLayout.LayoutParams viewport = new FrameLayout.LayoutParams(-1, -1);
        addView(scroll, viewport);
        header = new LinearLayout(context);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(context, 16), 0, dp(context, 16), 0);
        // A simple tint follows the content immediately, without blur or captured imagery.
        header.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.TOP_BOTTOM,
                        new int[] {0xc9101113, 0x35101113}));
        FrameLayout glass = new FrameLayout(context);
        glass.addView(header, new FrameLayout.LayoutParams(-1, -1));
        View hairline = new View(context);
        hairline.setBackgroundColor(0x12ffffff);
        glass.addView(hairline, new FrameLayout.LayoutParams(-1, 1, Gravity.BOTTOM));
        addView(glass, new FrameLayout.LayoutParams(-1, dp(context, 48), Gravity.TOP));
        searchLoading = new FrameLayout(context);
        searchLoading.setBackgroundColor(0x30101113);
        searchLoading.setFocusable(false);
        searchLoading.setClickable(false);
        searchLoading.setVisibility(GONE);
        LinearLayout progressPanel = new LinearLayout(context);
        progressPanel.setGravity(Gravity.CENTER_VERTICAL);
        progressPanel.setPadding(
                dp(context, 22), dp(context, 18), dp(context, 22), dp(context, 18));
        progressPanel.setBackground(surface(0xee191d24, dp(context, 12)));
        ProgressBar progress = new ProgressBar(context);
        progress.setIndeterminate(true);
        progress.setIndeterminateTintList(ColorStateList.valueOf(WHITE));
        progressPanel.addView(
                progress, new LinearLayout.LayoutParams(dp(context, 26), dp(context, 26)));
        TextView searching = label(context, "Searching…", 16, WHITE, false);
        searching.setAccessibilityLiveRegion(ACCESSIBILITY_LIVE_REGION_POLITE);
        LinearLayout.LayoutParams searchingBounds = new LinearLayout.LayoutParams(-2, -2);
        searchingBounds.leftMargin = dp(context, 16);
        progressPanel.addView(searching, searchingBounds);
        searchLoading.addView(progressPanel, new FrameLayout.LayoutParams(-2, -2, Gravity.CENTER));
        FrameLayout.LayoutParams loadingBounds = new FrameLayout.LayoutParams(-1, -1);
        loadingBounds.topMargin = dp(context, 48);
        addView(searchLoading, loadingBounds);
        buildHeader();
    }

    private void buildHeader() {
        header.removeAllViews();
        categoryButtons.clear();
        TextView brand = label(getContext(), "Autolycus", 19, WHITE, true);
        header.addView(brand, new LinearLayout.LayoutParams(dp(getContext(), 116), -2));
        String[] ids = {"all", "movie", "series", "library"};
        String[] names = {"For you", "Movies", "Series", "My library"};
        for (int i = 0; i < names.length; i++) {
            String id = ids[i];
            TextView button = action(getContext(), names[i], false);
            button.setTextSize(14);
            button.setPadding(dp(getContext(), 10), 0, dp(getContext(), 10), 0);
            button.setTag(id);
            button.setOnClickListener(v -> setCategory(id));
            header.addView(button, new LinearLayout.LayoutParams(-2, dp(getContext(), 40)));
            categoryButtons.add(button);
        }
        View gap = new View(getContext());
        header.addView(gap, new LinearLayout.LayoutParams(0, 1, 1));
        TextView search = action(getContext(), "", false);
        search.setContentDescription("Search movies and series");
        search.setCompoundDrawablesWithIntrinsicBounds(
                new Glyph(getContext(), true), null, null, null);
        search.setPadding(dp(getContext(), 8), 0, dp(getContext(), 8), 0);
        search.setOnClickListener(v -> openSearch());
        header.addView(
                search, new LinearLayout.LayoutParams(dp(getContext(), 40), dp(getContext(), 40)));
        profile = action(getContext(), "Profile", false);
        profile.setTextSize(13);
        profile.setSingleLine(true);
        profile.setEllipsize(TextUtils.TruncateAt.END);
        profile.setContentDescription("Switch profile");
        profile.setCompoundDrawablePadding(dp(getContext(), 10));
        profile.setCompoundDrawablesWithIntrinsicBounds(
                new Glyph(getContext(), false), null, null, null);
        profile.setOnClickListener(
                v -> {
                    setSearchLoading(false);
                    listener.onProfiles();
                });
        LinearLayout.LayoutParams profileLayout =
                new LinearLayout.LayoutParams(dp(getContext(), 142), dp(getContext(), 40));
        profileLayout.leftMargin = dp(getContext(), 12);
        header.addView(profile, profileLayout);
    }

    private void updateHeaderTint() {
        boolean scrolled = scroll.getScrollY() > dp(getContext(), 24);
        if (scrolled == scrolledHeader) return;
        scrolledHeader = scrolled;
        header.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.TOP_BOTTOM,
                        scrolled
                                ? new int[] {0xf4101113, 0xee101113}
                                : new int[] {0xc9101113, 0x35101113}));
    }

    private void styleHeroAction(TextView button, boolean primary) {
        button.setOnFocusChangeListener(
                (view, focused) -> {
                    view.animate().cancel();
                    view.animate()
                            .scaleX(focused ? 1.06f : 1f)
                            .scaleY(focused ? 1.06f : 1f)
                            .setDuration(140)
                            .start();
                    view.setBackground(
                            surface(
                                    primary
                                            ? focused ? WHITE : 0xffc1c4ca
                                            : focused ? 0xff444a55 : 0x99272a31,
                                    dp(getContext(), 6)));
                    button.setTextColor(primary ? BACKGROUND : WHITE);
                });
    }

    public void render(JSONObject value) {
        preserveFocus();
        boolean keepSearch = searchResults;
        catalog = value == null ? new JSONObject() : value;
        library.clear();
        shelves.clear();
        addObjects(library, catalog.optJSONArray("library"));
        addObjects(shelves, catalog.optJSONArray("shelves"));
        JSONObject user = catalog.optJSONObject("user");
        JSONObject activeProfile = catalog.optJSONObject("active_profile");
        if (activeProfile != null && !activeProfile.optString("name", "").isEmpty())
            profile.setText(activeProfile.optString("name"));
        else if (user != null) profile.setText(user.optString("name", "Profile"));
        if (keepSearch) showSearchResults(searchQuery, refreshedSearchItems());
        else {
            searchResults = false;
            rebuild();
        }
    }

    public void setCategory(String value) {
        setSearchLoading(false);
        if (value == null) value = "all";
        category = value;
        searchResults = false;
        lastMovie = "";
        rebuild();
    }

    public void setSearchLoading(boolean loading) {
        searchLoading.setVisibility(loading ? VISIBLE : GONE);
        if (navigationDebug != null)
            navigationDebug.edit().putBoolean("search_loading", loading).apply();
    }

    public boolean isSearchLoading() {
        return searchLoading.getVisibility() == VISIBLE;
    }

    public void showSearchResults(String query, JSONArray items) {
        setSearchLoading(false);
        preserveFocus();
        searchResults = true;
        searchQuery = query == null ? "" : query;
        searchItems = items == null ? new JSONArray() : items;
        content.removeAllViews();
        content.setPadding(0, dp(getContext(), 48), 0, dp(getContext(), 40));
        resetRows();
        TextView heading =
                label(
                        getContext(),
                        query == null || query.isEmpty()
                                ? "Search your collection"
                                : "Results for “" + query + "”",
                        28,
                        WHITE,
                        true);
        heading.setPadding(
                dp(getContext(), 24),
                dp(getContext(), 24),
                dp(getContext(), 24),
                dp(getContext(), 16));
        content.addView(heading);
        List<JSONObject> titles = new ArrayList<>();
        addObjects(titles, searchItems);
        if (titles.isEmpty()) {
            TextView empty =
                    label(
                            getContext(),
                            "No matching titles. Try another title or year.",
                            16,
                            MUTED,
                            false);
            empty.setPadding(dp(getContext(), 24), dp(getContext(), 24), dp(getContext(), 24), 0);
            content.addView(empty);
            initialFocus = categoryButtons.get(0);
        } else {
            for (int i = 0; i < titles.size(); i += 5)
                addShelf(
                        i == 0 ? "Movies and series" : "",
                        titles.subList(i, Math.min(i + 5, titles.size())),
                        false);
            initialFocus = rows.size() > 1 ? rows.get(1).get(0) : categoryButtons.get(0);
        }
        restoreFocusAfterLayout();
    }

    private JSONArray refreshedSearchItems() {
        JSONArray refreshed = new JSONArray();
        String[] progressFields = {
            "progress", "watch_progress", "resume_path", "next_episode", "files", "path", "owned"
        };
        for (int i = 0; i < searchItems.length(); i++) {
            JSONObject previous = searchItems.optJSONObject(i);
            if (previous == null) continue;
            JSONObject next = previous;
            try {
                next = new JSONObject(previous.toString());
                String id = previous.optString("id", "");
                String imdb = previous.optString("imdb_id", "");
                for (JSONObject local : library) {
                    boolean same =
                            !id.isEmpty() && id.equals(local.optString("id", ""))
                                    || !imdb.isEmpty()
                                            && imdb.equals(local.optString("imdb_id", ""));
                    if (!same) continue;
                    for (String field : progressFields)
                        if (local.has(field)) next.put(field, local.opt(field));
                    break;
                }
            } catch (org.json.JSONException ignored) {
                // Retain a valid existing search result if a refresh cannot be merged.
            }
            refreshed.put(next);
        }
        return refreshed;
    }

    public boolean onBack() {
        if (isSearchLoading()) {
            setSearchLoading(false);
            return true;
        }
        if (searchDialog != null && searchDialog.isShowing()) {
            searchDialog.dismiss();
            return true;
        }
        if (searchResults || !"all".equals(category)) {
            category = "all";
            searchResults = false;
            rebuild();
            return true;
        }
        View focused = findFocus();
        if (focused != null
                && !rows.isEmpty()
                && (focused instanceof PosterCard || scroll.getScrollY() > dp(getContext(), 20))) {
            if (initialFocus != null) focus(initialFocus);
            else scrollToPosition(0, true);
            return true;
        }
        return false;
    }

    public void preserveFocus() {
        View focused = findFocus();
        rememberFocus(focused);
    }

    public void requestInitialFocus() {
        if (!searchResults
                && savedFocusRow >= 0
                && savedFocusRow < 2
                && savedFocusRow < rows.size()) {
            List<View> savedRow = rows.get(savedFocusRow);
            View target = savedRow.get(Math.min(savedFocusColumn, savedRow.size() - 1));
            focus(target);
            scrollToPosition(0, false);
            postOnAnimation(
                    () -> {
                        if (findFocus() == target && !searchResults && savedFocusRow < 2) {
                            scrollToPosition(0, false);
                            recordNavigationFocus(target);
                        }
                    });
            return;
        }
        if (!lastMovie.isEmpty()) {
            if (savedFocusRow >= 2 && savedFocusRow < rows.size()) {
                for (View view : rows.get(savedFocusRow)) {
                    if (view instanceof PosterCard
                            && lastMovie.equals(key(((PosterCard) view).item))) {
                        focus(view);
                        return;
                    }
                }
            }
            for (List<View> row : rows) {
                for (View view : row) {
                    if (view instanceof PosterCard
                            && lastMovie.equals(key(((PosterCard) view).item))) {
                        focus(view);
                        return;
                    }
                }
            }
        }
        if (initialFocus != null) focus(initialFocus);
    }

    private void restoreFocusAfterLayout() {
        if (pendingFocusRestore != null && content.getViewTreeObserver().isAlive())
            content.getViewTreeObserver().removeOnGlobalLayoutListener(pendingFocusRestore);
        pendingFocusRestore =
                () -> {
                    if (content.getViewTreeObserver().isAlive())
                        content.getViewTreeObserver()
                                .removeOnGlobalLayoutListener(pendingFocusRestore);
                    pendingFocusRestore = null;
                    requestInitialFocus();
                    updateHeaderTint();
                };
        content.getViewTreeObserver().addOnGlobalLayoutListener(pendingFocusRestore);
        content.requestLayout();
    }

    private void resetRows() {
        posters.clear();
        rows.clear();
        sections.clear();
        rails.clear();
        List<View> top = new ArrayList<>();
        for (int i = 0; i < header.getChildCount(); i++) {
            View child = header.getChildAt(i);
            if (child.isFocusable()) top.add(child);
        }
        registerRow(top, null, null);
        for (TextView button : categoryButtons) {
            boolean active = category.equals(button.getTag());
            button.setTextColor(active ? WHITE : MUTED);
            button.setTypeface(Typeface.DEFAULT, active ? Typeface.BOLD : Typeface.NORMAL);
        }
    }

    private void rebuild() {
        setSearchLoading(false);
        content.removeAllViews();
        content.setPadding(0, 0, 0, dp(getContext(), 40));
        resetRows();
        List<JSONObject> local = filter(library, category);
        List<JSONObject> continuing = new ArrayList<>();
        for (JSONObject item : local) {
            JSONObject progress = item.optJSONObject("progress");
            if (progress != null
                    && (!progress.optBoolean("completed") || item.optBoolean("next_episode")))
                continuing.add(item);
        }
        Collections.sort(continuing, (a, b) -> Double.compare(updated(b), updated(a)));
        JSONObject feature =
                !continuing.isEmpty()
                        ? continuing.get(0)
                        : !local.isEmpty() ? local.get(0) : firstDiscovery();
        if (feature != null) addHero(feature);
        else content.setPadding(0, dp(getContext(), 48), 0, dp(getContext(), 40));
        TextView tools =
                label(
                        getContext(),
                        "YOUR LIBRARY     Ready to play · " + local.size() + " titles",
                        11,
                        0xff9aa9bd,
                        true);
        tools.setLetterSpacing(.12f);
        tools.setPadding(
                dp(getContext(), 24),
                dp(getContext(), 6),
                dp(getContext(), 24),
                dp(getContext(), 18));
        content.addView(tools);
        addShelf("Continue watching", continuing, true);
        addShelf("Recently added", local.subList(0, Math.min(24, local.size())), false);
        addShelf("Your movies", filter(local, "movie"), false);
        addShelf("Your series", filter(local, "series"), false);
        if (!"library".equals(category)) {
            for (JSONObject shelf : shelves) {
                List<JSONObject> items = new ArrayList<>();
                addObjects(items, shelf.optJSONArray("items"));
                addShelf(shelf.optString("title", "Discover"), filter(items, category), false);
            }
        }
        if (feature == null && local.isEmpty() && shelves.isEmpty()) {
            TextView empty =
                    label(
                            getContext(),
                            "Your collection is ready for its first movie.",
                            22,
                            WHITE,
                            false);
            empty.setPadding(dp(getContext(), 24), dp(getContext(), 70), dp(getContext(), 24), 0);
            content.addView(empty);
            initialFocus = categoryButtons.get(0);
        }
        restoreFocusAfterLayout();
        refreshArtworkSoon();
        updateHeaderTint();
    }

    private JSONObject firstDiscovery() {
        for (JSONObject shelf : shelves) {
            JSONArray items = shelf.optJSONArray("items");
            if (items != null && items.length() > 0) return items.optJSONObject(0);
        }
        return null;
    }

    private void addHero(JSONObject item) {
        FrameLayout hero = new FrameLayout(getContext());
        hero.setClipChildren(true);
        hero.setBackgroundColor(BACKGROUND);
        content.addView(hero, new LinearLayout.LayoutParams(-1, dp(getContext(), 478)));
        ImageView background = new ImageView(getContext());
        background.setScaleType(ImageView.ScaleType.CENTER_CROP);
        background.setCropToPadding(true);
        FrameLayout.LayoutParams art = new FrameLayout.LayoutParams(-1, -1);
        hero.addView(background, art);
        String backdrop = item.optString("background", "");
        if (backdrop.isEmpty()) backdrop = item.optString("poster", "");
        artwork.load(background, backdrop, 1600, 900);
        View shade = new View(getContext());
        shade.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.LEFT_RIGHT,
                        new int[] {0xff101113, 0xf2101113, 0x30101113}));
        hero.addView(shade, new FrameLayout.LayoutParams(-1, -1));
        View bottom = new View(getContext());
        bottom.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.BOTTOM_TOP,
                        new int[] {0xff101113, 0x00101113}));
        FrameLayout.LayoutParams fade =
                new FrameLayout.LayoutParams(-1, dp(getContext(), 130), Gravity.BOTTOM);
        hero.addView(bottom, fade);
        LinearLayout copy = new LinearLayout(getContext());
        copy.setOrientation(LinearLayout.VERTICAL);
        copy.setClipChildren(false);
        copy.setClipToPadding(false);
        copy.setPadding(dp(getContext(), 6), 0, dp(getContext(), 6), 0);
        copy.setGravity(Gravity.CENTER_VERTICAL);
        FrameLayout.LayoutParams copyBounds =
                new FrameLayout.LayoutParams(dp(getContext(), 550), -1);
        copyBounds.leftMargin = dp(getContext(), 18);
        copyBounds.topMargin = dp(getContext(), 66);
        copyBounds.bottomMargin = dp(getContext(), 20);
        hero.addView(copy, copyBounds);
        TextView eyebrow =
                label(
                        getContext(),
                        item.optBoolean("owned") ? "FROM YOUR LIBRARY" : "DISCOVER YOUR NEXT WATCH",
                        10,
                        0xffaab3c4,
                        true);
        eyebrow.setLetterSpacing(.2f);
        copy.addView(eyebrow);
        FrameLayout titleSlot = new FrameLayout(getContext());
        LinearLayout.LayoutParams titleBounds =
                new LinearLayout.LayoutParams(dp(getContext(), 505), dp(getContext(), 110));
        titleBounds.topMargin = dp(getContext(), 16);
        titleBounds.bottomMargin = dp(getContext(), 12);
        copy.addView(titleSlot, titleBounds);
        TextView title = label(getContext(), item.optString("title", ""), 38, WHITE, true);
        title.setMaxLines(3);
        title.setLineSpacing(0, 1.02f);
        title.setGravity(Gravity.CENTER_VERTICAL);
        titleSlot.addView(title, new FrameLayout.LayoutParams(-1, -1));
        String logo = item.optString("logo", "");
        if (!logo.isEmpty() && !"null".equals(logo)) {
            ImageView titleLogo = new ImageView(getContext());
            titleLogo.setScaleType(ImageView.ScaleType.FIT_START);
            titleSlot.addView(
                    titleLogo,
                    new FrameLayout.LayoutParams(
                            dp(getContext(), 400), -1, Gravity.LEFT | Gravity.CENTER_VERTICAL));
            titleLogo.setContentDescription(item.optString("title"));
            artwork.load(titleLogo, logo, 800, 260, () -> title.setVisibility(INVISIBLE));
        }
        TextView metadata = label(getContext(), metadata(item), 13, 0xffb7bec9, false);
        copy.addView(metadata);
        TextView synopsis =
                label(getContext(), item.optString("overview", ""), 14, 0xffd2d5dc, false);
        synopsis.setMaxLines(3);
        synopsis.setEllipsize(TextUtils.TruncateAt.END);
        synopsis.setLineSpacing(dp(getContext(), 4), 1f);
        LinearLayout.LayoutParams synopsisBounds =
                new LinearLayout.LayoutParams(dp(getContext(), 505), -2);
        synopsisBounds.topMargin = dp(getContext(), 14);
        synopsisBounds.bottomMargin = dp(getContext(), 20);
        copy.addView(synopsis, synopsisBounds);
        LinearLayout actions = new LinearLayout(getContext());
        actions.setGravity(Gravity.CENTER_VERTICAL);
        actions.setClipChildren(false);
        actions.setClipToPadding(false);
        actions.setPadding(0, dp(getContext(), 4), 0, dp(getContext(), 6));
        copy.addView(actions);
        String playText =
                item.optBoolean("owned")
                        ? item.optJSONObject("progress") != null ? "Continue watching" : "Play"
                        : "Watch options";
        TextView play = action(getContext(), "▶  " + playText, true);
        styleHeroAction(play, true);
        play.setContentDescription(playText + " " + item.optString("title"));
        play.setOnClickListener(
                v -> {
                    setSearchLoading(false);
                    if (item.optBoolean("owned")) listener.onPlay(item, playPath(item));
                    else listener.onDetails(item);
                });
        actions.addView(play, new LinearLayout.LayoutParams(-2, dp(getContext(), 44)));
        TextView more = action(getContext(), "More info", false);
        styleHeroAction(more, false);
        more.setBackground(surface(0x99272a31, dp(getContext(), 6)));
        more.setOnClickListener(
                v -> {
                    setSearchLoading(false);
                    listener.onDetails(item);
                });
        LinearLayout.LayoutParams moreBounds =
                new LinearLayout.LayoutParams(-2, dp(getContext(), 44));
        moreBounds.leftMargin = dp(getContext(), 12);
        actions.addView(more, moreBounds);
        List<View> actionRow = new ArrayList<>();
        actionRow.add(play);
        actionRow.add(more);
        registerRow(actionRow, hero, null);
        initialFocus = play;
    }

    private void addShelf(String heading, List<JSONObject> items, boolean continuing) {
        if (items.isEmpty()) return;
        LinearLayout section = new LinearLayout(getContext());
        section.setOrientation(LinearLayout.VERTICAL);
        section.setClipChildren(false);
        section.setPadding(0, 0, 0, dp(getContext(), 22));
        content.addView(section, new LinearLayout.LayoutParams(-1, -2));
        if (!heading.isEmpty()) {
            TextView title = label(getContext(), heading, 19, WHITE, true);
            title.setPadding(dp(getContext(), 24), 0, dp(getContext(), 24), dp(getContext(), 10));
            section.addView(title);
        }
        HorizontalScrollView rail =
                new HorizontalScrollView(getContext()) {
                    @Override
                    protected int computeScrollDeltaToGetChildRectOnScreen(Rect rect) {
                        return 0;
                    }
                };
        rail.setHorizontalScrollBarEnabled(false);
        rail.setOverScrollMode(OVER_SCROLL_NEVER);
        rail.setFocusable(false);
        rail.setOnScrollChangeListener(
                (View.OnScrollChangeListener)
                        (view, x, y, oldX, oldY) -> {
                            refreshArtworkSoon();
                        });
        rail.setClipChildren(false);
        rail.setClipToPadding(false);
        rail.setPadding(
                dp(getContext(), 24),
                dp(getContext(), 8),
                dp(getContext(), 24),
                dp(getContext(), 8));
        section.addView(rail, new LinearLayout.LayoutParams(-1, -2));
        LinearLayout strip = new LinearLayout(getContext());
        strip.setOrientation(LinearLayout.HORIZONTAL);
        strip.setClipChildren(false);
        strip.setClipToPadding(false);
        rail.addView(strip, new HorizontalScrollView.LayoutParams(-2, -2));
        int width =
                (getResources().getDisplayMetrics().widthPixels - dp(getContext(), 48 + 4 * 18))
                        / 5;
        List<View> cards = new ArrayList<>();
        for (int i = 0; i < Math.min(100, items.size()); i++) {
            PosterCard card = new PosterCard(items.get(i), width, continuing);
            posters.add(card);
            LinearLayout.LayoutParams cardBounds = new LinearLayout.LayoutParams(width, -2);
            if (i > 0) cardBounds.leftMargin = dp(getContext(), 18);
            strip.addView(card, cardBounds);
            cards.add(card);
        }
        registerRow(cards, section, rail);
    }

    private void registerRow(List<View> views, View section, HorizontalScrollView rail) {
        final int rowIndex = rows.size();
        rows.add(views);
        sections.add(section);
        rails.add(rail);
        for (int i = 0; i < views.size(); i++) {
            final int column = i;
            View view = views.get(i);
            view.setOnKeyListener(
                    (v, keyCode, event) -> {
                        if (event.getAction() != KeyEvent.ACTION_DOWN) return false;
                        if (keyCode == KeyEvent.KEYCODE_MENU) {
                            setSearchLoading(false);
                            if (v instanceof PosterCard) listener.onDetails(((PosterCard) v).item);
                            else listener.onSettings();
                            return true;
                        }
                        if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT
                                || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) {
                            int next =
                                    Math.max(
                                            0,
                                            Math.min(
                                                    views.size() - 1,
                                                    column
                                                            + (keyCode
                                                                            == KeyEvent
                                                                                    .KEYCODE_DPAD_RIGHT
                                                                    ? 1
                                                                    : -1)));
                            preferredColumn = next;
                            focus(views.get(next));
                            return true;
                        }
                        if (keyCode == KeyEvent.KEYCODE_DPAD_UP
                                || keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                            int next = rowIndex + (keyCode == KeyEvent.KEYCODE_DPAD_DOWN ? 1 : -1);
                            if (next >= 0 && next < rows.size()) {
                                List<View> target = rows.get(next);
                                focus(target.get(Math.min(preferredColumn, target.size() - 1)));
                            }
                            return true;
                        }
                        return false;
                    });
        }
    }

    private void focus(View target) {
        rememberFocus(target);
        target.requestFocus();
        if (target instanceof PosterCard) ((PosterCard) target).requestArtwork();
        for (int row = 0; row < rows.size(); row++) {
            if (!rows.get(row).contains(target)) continue;
            if (row < 2 && !searchResults) scrollToPosition(0, true);
            else if (sections.get(row) != null)
                scrollToPosition(
                        Math.max(0, sections.get(row).getTop() - dp(getContext(), 58)), true);
            HorizontalScrollView rail = rails.get(row);
            if (rail != null) {
                int left = target.getLeft(), right = target.getRight();
                int current = rail.getScrollX();
                int visible = rail.getWidth() - rail.getPaddingLeft() - rail.getPaddingRight();
                if (left < current) rail.smoothScrollTo(left, 0);
                else if (right > current + visible) rail.smoothScrollTo(right - visible, 0);
            }
            break;
        }
        refreshArtworkSoon();
    }

    private void rememberFocus(View focused) {
        if (focused == null) return;
        for (int row = 0; row < rows.size(); row++) {
            int column = rows.get(row).indexOf(focused);
            if (column < 0) continue;
            savedFocusRow = row;
            savedFocusColumn = column;
            lastMovie = focused instanceof PosterCard ? key(((PosterCard) focused).item) : "";
            return;
        }
    }

    private void scrollToPosition(int position, boolean animate) {
        if (verticalScroll != null) {
            verticalScroll.cancel();
            verticalScroll = null;
        }
        int target =
                Math.max(
                        0,
                        Math.min(position, Math.max(0, content.getHeight() - scroll.getHeight())));
        if (!animate || Math.abs(target - scroll.getScrollY()) < dp(getContext(), 2)) {
            scroll.scrollTo(0, target);
            return;
        }
        verticalScroll = ValueAnimator.ofInt(scroll.getScrollY(), target);
        verticalScroll.setDuration(220);
        verticalScroll.setInterpolator(new DecelerateInterpolator());
        verticalScroll.addUpdateListener(
                animation -> scroll.scrollTo(0, (Integer) animation.getAnimatedValue()));
        verticalScroll.start();
    }

    private void refreshArtworkSoon() {
        if (refreshPosted) return;
        refreshPosted = true;
        postDelayed(refreshPosters, 65);
    }

    private void recordNavigationFocus(View focused) {
        if (navigationDebug == null || focused == null) return;
        for (int row = 0; row < rows.size(); row++) {
            int column = rows.get(row).indexOf(focused);
            if (column < 0) continue;
            CharSequence description = focused.getContentDescription();
            if (description == null && focused instanceof TextView)
                description = ((TextView) focused).getText();
            navigationDebug
                    .edit()
                    .putString(
                            "focused_label",
                            description == null
                                    ? focused.getClass().getSimpleName()
                                    : description.toString())
                    .putInt("row", row)
                    .putInt("column", column)
                    .putInt("scroll_y", scroll.getScrollY())
                    .putString("category", category)
                    .putBoolean("search_results", searchResults)
                    .putString(
                            "item_id",
                            focused instanceof PosterCard ? key(((PosterCard) focused).item) : "")
                    .apply();
            return;
        }
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (BuildConfig.DEBUG)
            getViewTreeObserver().addOnGlobalFocusChangeListener(navigationObserver);
    }

    @Override
    protected void onDetachedFromWindow() {
        if (pendingFocusRestore != null && content.getViewTreeObserver().isAlive()) {
            content.getViewTreeObserver().removeOnGlobalLayoutListener(pendingFocusRestore);
            pendingFocusRestore = null;
        }
        if (verticalScroll != null) {
            verticalScroll.cancel();
            verticalScroll = null;
        }
        if (BuildConfig.DEBUG && getViewTreeObserver().isAlive())
            getViewTreeObserver().removeOnGlobalFocusChangeListener(navigationObserver);
        removeCallbacks(refreshPosters);
        removeCallbacks(recordSettledFocus);
        refreshPosted = false;
        super.onDetachedFromWindow();
    }

    private void openSearch() {
        setSearchLoading(false);
        Dialog dialog = new Dialog(getContext());
        searchDialog = dialog;
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout panel = new LinearLayout(getContext());
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(
                dp(getContext(), 20),
                dp(getContext(), 18),
                dp(getContext(), 20),
                dp(getContext(), 18));
        panel.setBackground(surface(0xff191d24, dp(getContext(), 18)));
        TextView title = label(getContext(), "Search movies and series", 22, WHITE, true);
        panel.addView(title);
        EditText query = new EditText(getContext());
        query.setSingleLine(true);
        query.setTextSize(18);
        query.setTextColor(WHITE);
        query.setHintTextColor(MUTED);
        query.setHint("A title, actor or year");
        query.setContentDescription("Search movies and series");
        query.setImeOptions(EditorInfo.IME_ACTION_SEARCH | EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        panel.addView(query, new LinearLayout.LayoutParams(-1, dp(getContext(), 54)));
        query.setOnEditorActionListener(
                (view, action, event) -> {
                    if (action == EditorInfo.IME_ACTION_SEARCH
                            || action == EditorInfo.IME_ACTION_DONE
                            || event != null
                                    && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                                    && event.getAction() == KeyEvent.ACTION_UP) {
                        String value = query.getText().toString().trim();
                        ((InputMethodManager)
                                        getContext().getSystemService(Context.INPUT_METHOD_SERVICE))
                                .hideSoftInputFromWindow(query.getWindowToken(), 0);
                        dialog.dismiss();
                        listener.onSearch(value);
                        return true;
                    }
                    return false;
                });
        dialog.setContentView(panel);
        Window window = dialog.getWindow();
        window.setBackgroundDrawableResource(android.R.color.transparent);
        window.setGravity(Gravity.TOP | Gravity.CENTER_HORIZONTAL);
        WindowManager.LayoutParams params = window.getAttributes();
        params.y = dp(getContext(), 48);
        window.setAttributes(params);
        window.setLayout(
                Math.min(
                        dp(getContext(), 560),
                        getResources().getDisplayMetrics().widthPixels - dp(getContext(), 64)),
                -2);
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_PAN);
        window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
        window.setDimAmount(.55f);
        dialog.setOnShowListener(
                ignored -> {
                    query.requestFocus();
                    query.post(
                            () ->
                                    ((InputMethodManager)
                                                    getContext()
                                                            .getSystemService(
                                                                    Context.INPUT_METHOD_SERVICE))
                                            .showSoftInput(
                                                    query, InputMethodManager.SHOW_IMPLICIT));
                });
        dialog.show();
    }

    private final class PosterCard extends LinearLayout {
        final JSONObject item;
        private final FrameLayout poster;
        private final ImageView play;
        private final TextView name;
        private final ImageView image;
        private final int artworkWidth;
        private boolean artworkRequested;

        PosterCard(JSONObject item, int width, boolean continuing) {
            super(NativeHomeView.this.getContext());
            this.item = item;
            setOrientation(VERTICAL);
            setFocusable(true);
            setDefaultFocusHighlightEnabled(false);
            setClickable(true);
            setClipChildren(false);
            setContentDescription(
                    (item.optBoolean("owned") ? "Play " : "View ") + item.optString("title"));
            poster = new FrameLayout(getContext());
            poster.setBackground(surface(0xff1a1d24, dp(getContext(), 8)));
            poster.setClipToOutline(true);
            addView(poster, new LinearLayout.LayoutParams(-1, width * 3 / 2));
            artworkWidth = width;
            image = new ImageView(getContext());
            image.setScaleType(ImageView.ScaleType.CENTER_CROP);
            poster.addView(image, new FrameLayout.LayoutParams(-1, -1));
            double rating = item.optDouble("rating", 0);
            if (rating > 0) {
                TextView badge =
                        label(
                                getContext(),
                                "★ " + String.format(Locale.ROOT, "%.1f", rating),
                                11,
                                0xffeab765,
                                true);
                badge.setPadding(
                        dp(getContext(), 5),
                        dp(getContext(), 4),
                        dp(getContext(), 5),
                        dp(getContext(), 4));
                badge.setBackground(surface(0xdd101113, dp(getContext(), 5)));
                FrameLayout.LayoutParams ratingBounds =
                        new FrameLayout.LayoutParams(-2, -2, Gravity.TOP | Gravity.RIGHT);
                ratingBounds.setMargins(
                        dp(getContext(), 7), dp(getContext(), 7), dp(getContext(), 7), 0);
                poster.addView(badge, ratingBounds);
            }
            play = new ImageView(getContext());
            play.setImageResource(R.drawable.autolycus_poster_play);
            play.setScaleType(ImageView.ScaleType.FIT_CENTER);
            play.setPadding(
                    dp(getContext(), 9),
                    dp(getContext(), 9),
                    dp(getContext(), 9),
                    dp(getContext(), 9));
            play.setBackground(surface(0xfff4f4f5, dp(getContext(), 20)));
            play.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            play.setVisibility(INVISIBLE);
            poster.addView(
                    play,
                    new FrameLayout.LayoutParams(
                            dp(getContext(), 40), dp(getContext(), 40), Gravity.CENTER));
            JSONObject progress = item.optJSONObject("watch_progress");
            if (progress == null) progress = item.optJSONObject("progress");
            double percent = percent(progress);
            if (percent > 0) {
                FrameLayout track = new FrameLayout(getContext());
                track.setBackgroundColor(0x665d6470);
                poster.addView(
                        track,
                        new FrameLayout.LayoutParams(-1, dp(getContext(), 3), Gravity.BOTTOM));
                View filled = new View(getContext());
                filled.setBackgroundColor(0xff6297ff);
                track.addView(
                        filled,
                        new FrameLayout.LayoutParams(
                                Math.max(dp(getContext(), 2), (int) (width * percent / 100)), -1));
            }
            name = label(getContext(), item.optString("title", ""), 13, 0xffe3e5e9, false);
            name.setSingleLine(true);
            name.setEllipsize(TextUtils.TruncateAt.END);
            LinearLayout.LayoutParams nameBounds = new LinearLayout.LayoutParams(-1, -2);
            nameBounds.topMargin = dp(getContext(), 10);
            addView(name, nameBounds);
            TextView meta =
                    label(
                            getContext(),
                            continuing
                                    ? item.optBoolean("next_episode")
                                            ? "Next episode"
                                            : Math.round(percent(item.optJSONObject("progress")))
                                                    + "% watched"
                                    : (item.optInt("year", 0) == 0
                                                    ? ""
                                                    : item.optInt("year") + " · ")
                                            + ("series".equals(item.optString("kind"))
                                                    ? "Series"
                                                    : "Movie"),
                            11,
                            0xff808792,
                            false);
            LinearLayout.LayoutParams metaBounds = new LinearLayout.LayoutParams(-1, -2);
            metaBounds.topMargin = dp(getContext(), 4);
            addView(meta, metaBounds);
            setOnFocusChangeListener(
                    (view, focused) -> {
                        poster.animate().cancel();
                        poster.animate()
                                .scaleX(focused ? 1.035f : 1f)
                                .scaleY(focused ? 1.035f : 1f)
                                .translationZ(focused ? dp(getContext(), 8) : 0)
                                .setDuration(160)
                                .start();
                        play.setVisibility(
                                focused && item.optBoolean("owned") ? VISIBLE : INVISIBLE);
                        name.setTextColor(focused ? WHITE : 0xffe3e5e9);
                        name.setTypeface(
                                Typeface.DEFAULT, focused ? Typeface.BOLD : Typeface.NORMAL);
                        if (focused) lastMovie = key(item);
                    });
            setOnClickListener(
                    v -> {
                        setSearchLoading(false);
                        if (item.optBoolean("owned")) listener.onPlay(item, playPath(item));
                        else listener.onDetails(item);
                    });
            setOnLongClickListener(
                    v -> {
                        setSearchLoading(false);
                        listener.onDetails(item);
                        return true;
                    });
        }

        void requestArtwork() {
            if (artworkRequested) return;
            artworkRequested = true;
            artwork.load(
                    image,
                    item.optString("poster", ""),
                    Math.max(artworkWidth, 320),
                    Math.max(artworkWidth * 3 / 2, 480));
        }

        void releaseArtwork() {
            if (!artworkRequested) return;
            image.setTag(null);
            image.animate().cancel();
            image.setImageDrawable(null);
            image.setAlpha(1f);
            artworkRequested = false;
        }
    }

    static TextView label(Context context, String value, float size, int color, boolean bold) {
        TextView text = new TextView(context);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(color);
        text.setFontFeatureSettings("kern");
        text.setIncludeFontPadding(false);
        text.setTypeface(Typeface.DEFAULT, bold ? Typeface.BOLD : Typeface.NORMAL);
        return text;
    }

    static TextView action(Context context, String value, boolean primary) {
        TextView text = label(context, value, 13, primary ? BACKGROUND : WHITE, true);
        text.setGravity(Gravity.CENTER);
        text.setFocusable(true);
        text.setDefaultFocusHighlightEnabled(false);
        text.setClickable(true);
        text.setPadding(dp(context, 18), 0, dp(context, 18), 0);
        text.setBackground(surface(primary ? 0xffc1c4ca : Color.TRANSPARENT, dp(context, 6)));
        text.setOnFocusChangeListener(
                (view, focused) -> {
                    view.animate().cancel();
                    view.animate()
                            .scaleX(focused ? 1.025f : 1f)
                            .scaleY(focused ? 1.025f : 1f)
                            .setDuration(140)
                            .start();
                    if (primary)
                        view.setBackground(surface(focused ? WHITE : 0xffc1c4ca, dp(context, 6)));
                    else
                        view.setBackground(
                                surface(focused ? 0x24ffffff : Color.TRANSPARENT, dp(context, 6)));
                    text.setTextColor(primary ? BACKGROUND : focused ? WHITE : 0xffb9bdc5);
                });
        return text;
    }

    static GradientDrawable surface(int color, float radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(radius);
        return drawable;
    }

    static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static String playPath(JSONObject item) {
        String path = item.optString("resume_path", "");
        return path.isEmpty() ? item.optString("path", "") : path;
    }

    static double percent(JSONObject progress) {
        if (progress == null || progress.optDouble("duration", 0) <= 0) return 0;
        return Math.min(
                100,
                Math.max(0, progress.optDouble("position") / progress.optDouble("duration") * 100));
    }

    static String metadata(JSONObject item) {
        List<String> parts = new ArrayList<>();
        if (item.optDouble("rating", 0) > 0)
            parts.add("★ " + String.format(Locale.ROOT, "%.1f", item.optDouble("rating")));
        if (item.optInt("year", 0) > 0) parts.add(Integer.toString(item.optInt("year")));
        parts.add("series".equals(item.optString("kind")) ? "Series" : "Movie");
        if (!item.optString("runtime", "").isEmpty()) parts.add(item.optString("runtime"));
        if (item.optBoolean("owned")) parts.add("In your library");
        return TextUtils.join("   ·   ", parts);
    }

    private static String key(JSONObject item) {
        return item.optString("id", item.optString("imdb_id", item.optString("title")));
    }

    private static double updated(JSONObject item) {
        JSONObject progress = item.optJSONObject("progress");
        return progress == null ? 0 : progress.optDouble("updated", 0);
    }

    private static List<JSONObject> filter(List<JSONObject> source, String kind) {
        List<JSONObject> result = new ArrayList<>();
        for (JSONObject item : source)
            if ("all".equals(kind) || "library".equals(kind) || kind.equals(item.optString("kind")))
                result.add(item);
        return result;
    }

    private static void addObjects(List<JSONObject> target, JSONArray array) {
        if (array == null) return;
        for (int i = 0; i < array.length(); i++)
            if (array.optJSONObject(i) != null) target.add(array.optJSONObject(i));
    }

    private static final class Glyph extends Drawable {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final boolean search;
        private final int size;

        Glyph(Context context, boolean search) {
            this.search = search;
            size = dp(context, 23);
            paint.setColor(WHITE);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(dp(context, 1.7f));
            paint.setStrokeCap(Paint.Cap.ROUND);
        }

        @Override
        public void draw(Canvas canvas) {
            int save = canvas.save();
            canvas.translate(getBounds().left, getBounds().top);
            canvas.scale(getBounds().width() / 24f, getBounds().height() / 24f);
            paint.setStrokeWidth(1.8f);
            if (search) {
                canvas.drawCircle(10.5f, 10.5f, 6.6f, paint);
                canvas.drawLine(15.5f, 15.5f, 21, 21, paint);
            } else {
                canvas.drawCircle(12, 7.5f, 3.6f, paint);
                Path path = new Path();
                path.moveTo(4.5f, 21);
                path.lineTo(4.5f, 18.5f);
                path.cubicTo(4.5f, 12.5f, 19.5f, 12.5f, 19.5f, 18.5f);
                path.lineTo(19.5f, 21);
                canvas.drawPath(path, paint);
            }
            canvas.restoreToCount(save);
        }

        @Override
        public int getIntrinsicWidth() {
            return size;
        }

        @Override
        public int getIntrinsicHeight() {
            return size;
        }

        @Override
        public void setAlpha(int alpha) {
            paint.setAlpha(alpha);
        }

        @Override
        public void setColorFilter(ColorFilter filter) {
            paint.setColorFilter(filter);
        }

        @Override
        public int getOpacity() {
            return PixelFormat.TRANSLUCENT;
        }
    }
}
