package dev.quiet.autolycus;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Native OTT entry point; server, cookies, browsing and playback stay independently owned. */
public final class TvActivity extends Activity {
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newFixedThreadPool(3);
    private FrameLayout root;
    private AutolycusApi api;
    private CatalogRepository repository;
    private NativeHomeView home;
    private String server = "";
    private JSONObject catalog;
    private int generation;
    private boolean returnFromPlayer;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        root = new FrameLayout(this);
        root.setBackgroundColor(0xff101113);
        setContentView(root);
        immersive();
        server = getPreferences(MODE_PRIVATE).getString("server", "");
        if (server.isEmpty()) {
            String initial = getIntent().getStringExtra("server_url");
            if (initial != null && validServer(initial)) saveServer(initial);
        }
        if (server.isEmpty()) {
            showLoading();
            configureServer();
        } else {
            connect();
            if (configurationIntent(getIntent())) configureServer();
        }
    }

    private void immersive() {
        getWindow().getInsetsController().hide(WindowInsets.Type.systemBars());
        getWindow()
                .getInsetsController()
                .setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }

    private boolean validServer(String value) {
        Uri uri = Uri.parse(value);
        return ("http".equals(uri.getScheme()) || "https".equals(uri.getScheme()))
                && uri.getHost() != null
                && uri.getUserInfo() == null;
    }

    private void saveServer(String value) {
        server =
                Uri.parse(value)
                        .buildUpon()
                        .path("/")
                        .clearQuery()
                        .fragment(null)
                        .build()
                        .toString();
        getPreferences(MODE_PRIVATE).edit().putString("server", server).apply();
    }

    private boolean configurationIntent(Intent intent) {
        return "dev.quiet.tv.action.CONFIGURE_SERVER".equals(intent.getAction())
                || Intent.ACTION_APPLICATION_PREFERENCES.equals(intent.getAction());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (configurationIntent(intent)) configureServer();
        else if (catalog != null) resumeWatchNext();
    }

    private void connect() {
        api = new AutolycusApi(this, server);
        repository = new CatalogRepository(api);
        home = null;
        catalog = null;
        loadCatalog(true);
    }

    private void showLoading() {
        root.removeAllViews();
        ProgressBar progress = new ProgressBar(this);
        FrameLayout.LayoutParams params =
                new FrameLayout.LayoutParams(dp(44), dp(44), Gravity.CENTER);
        root.addView(progress, params);
    }

    private void loadCatalog(boolean loading) {
        final int request = ++generation;
        if (loading && home == null) showLoading();
        CatalogRepository selected = repository;
        worker.execute(
                () -> {
                    try {
                        JSONObject result = selected.loadLibrary();
                        main.post(
                                () -> {
                                    if (isDestroyed() || request != generation) return;
                                    catalog = result;
                                    showCatalog();
                                    loadDiscovery(request, selected);
                                });
                    } catch (AutolycusApi.ApiException error) {
                        main.post(
                                () -> {
                                    if (isDestroyed() || request != generation) return;
                                    if (error.statusCode == 401
                                            || error.statusCode == 403
                                            || error.statusCode == 400
                                                    && "User not logged in"
                                                            .equals(error.getMessage()))
                                        showLogin();
                                    else showConnectionError();
                                });
                    } catch (Exception error) {
                        main.post(
                                () -> {
                                    if (!isDestroyed() && request == generation)
                                        showConnectionError();
                                });
                    }
                });
    }

    private void loadDiscovery(int request, CatalogRepository selected) {
        worker.execute(
                () -> {
                    try {
                        JSONArray shelves = selected.loadDiscovery();
                        main.post(
                                () -> {
                                    if (isDestroyed()
                                            || request != generation
                                            || home == null
                                            || catalog == null) return;
                                    try {
                                        catalog.put("shelves", shelves);
                                        home.render(catalog);
                                    } catch (JSONException invalid) {
                                        // Keep the already displayed local collection usable.
                                    }
                                });
                    } catch (Exception unavailable) {
                        // External discovery must never block or replace the local collection.
                    }
                });
    }

    private void showConnectionError() {
        if (home != null) {
            Toast.makeText(
                            this,
                            "Unable to refresh. Your current catalogue is still available.",
                            Toast.LENGTH_LONG)
                    .show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Cannot reach Autolycus")
                .setMessage("Keep the server running and connect this TV to its network.")
                .setPositiveButton("Retry", (dialog, which) -> loadCatalog(true))
                .setNeutralButton("Server address", (dialog, which) -> configureServer())
                .setNegativeButton("Close", (dialog, which) -> finish())
                .show();
    }

    private void showCatalog() {
        if (home == null) {
            home =
                    new NativeHomeView(
                            this,
                            api,
                            new NativeHomeView.Listener() {
                                @Override
                                public void onDetails(JSONObject item) {
                                    details(item);
                                }

                                @Override
                                public void onPlay(JSONObject item, String path) {
                                    play(item, path);
                                }

                                @Override
                                public void onSearch(String query) {
                                    search(query);
                                }

                                @Override
                                public void onProfiles() {
                                    profiles();
                                }

                                @Override
                                public void onSettings() {
                                    configureServer();
                                }
                            });
            root.removeAllViews();
            root.addView(home, new FrameLayout.LayoutParams(-1, -1));
        }
        if (home.getParent() != root) {
            root.removeAllViews();
            root.addView(home, new FrameLayout.LayoutParams(-1, -1));
        }
        home.render(catalog);
        JSONArray library = catalog.optJSONArray("library");
        if (library != null) NativeWatchNext.reconcile(this, api, library);
        resumeWatchNext();
    }

    private void resumeWatchNext() {
        if (!NativeWatchNext.ACTION_RESUME.equals(getIntent().getAction()) || catalog == null)
            return;
        Intent intent = getIntent();
        setIntent(new Intent(this, TvActivity.class).setAction(Intent.ACTION_MAIN));
        JSONArray library = catalog.optJSONArray("library");
        JSONObject saved =
                library == null
                        ? null
                        : NativeWatchNext.resume(this, intent, server, api.getProfile(), library);
        if (saved == null) {
            Toast.makeText(
                            this,
                            "This title is no longer available in the current profile",
                            Toast.LENGTH_LONG)
                    .show();
            return;
        }
        play(saved.optJSONObject("item"), saved.optString("path"));
    }

    private void details(JSONObject item) {
        NativeDetailsDialog dialog =
                new NativeDetailsDialog(
                        this,
                        api,
                        item,
                        new NativeDetailsDialog.Listener() {
                            @Override
                            public void onPlay(JSONObject chosen, String path) {
                                play(chosen, path);
                            }

                            @Override
                            public void onOnline(JSONObject chosen) {
                                onlineSources(chosen);
                            }

                            @Override
                            public void onTrailer(JSONObject chosen) {
                                trailer(chosen);
                            }
                        });
        dialog.show();
        CatalogRepository selected = repository;
        worker.execute(
                () -> {
                    try {
                        JSONObject enriched = selected.detail(item);
                        main.post(
                                () -> {
                                    if (!isDestroyed() && dialog.isShowing())
                                        dialog.update(enriched);
                                });
                    } catch (Exception ignored) {
                        // The existing local details and Play action remain usable.
                    }
                });
    }

    private void play(JSONObject item, String path) {
        if (!item.optBoolean("owned", false) && (path == null || path.isEmpty())) {
            onlineSources(item);
            return;
        }
        String selected =
                path == null || path.isEmpty()
                        ? item.optString("resume_path", item.optString("path"))
                        : path;
        if (selected.isEmpty()) {
            onlineSources(item);
            return;
        }
        returnFromPlayer = true;
        NativePlayerActivity.open(this, item, selected, api.getServer(), api.getProfile());
    }

    private void search(String query) {
        int request = ++generation;
        CatalogRepository selected = repository;
        if (home != null) home.setSearchLoading(true);
        worker.execute(
                () -> {
                    try {
                        JSONArray result = selected.search(query);
                        main.post(
                                () -> {
                                    if (!isDestroyed()
                                            && request == generation
                                            && home != null
                                            && home.isSearchLoading())
                                        home.showSearchResults(query, result);
                                });
                    } catch (Exception ignored) {
                        main.post(
                                () -> {
                                    if (!isDestroyed()
                                            && request == generation
                                            && home != null
                                            && home.isSearchLoading()) {
                                        home.setSearchLoading(false);
                                        Toast.makeText(
                                                        this,
                                                        "Search is unavailable. Please try again.",
                                                        Toast.LENGTH_SHORT)
                                                .show();
                                    }
                                });
                    }
                });
    }

    private void profiles() {
        worker.execute(
                () -> {
                    try {
                        JSONObject result = api.get("/api/auth/profiles");
                        JSONArray profiles = result.optJSONArray("profiles");
                        if (profiles == null || profiles.length() == 0) return;
                        String[] names = new String[profiles.length()];
                        int active = 0;
                        for (int i = 0; i < names.length; i++) {
                            JSONObject profile = profiles.optJSONObject(i);
                            names[i] = profile.optString("name", "Profile");
                            if (profile.optString("id").equals(api.getProfile())) active = i;
                        }
                        final int checked = active;
                        main.post(
                                () -> {
                                    if (isDestroyed()) return;
                                    new AlertDialog.Builder(this)
                                            .setTitle("Who's watching?")
                                            .setSingleChoiceItems(
                                                    names,
                                                    checked,
                                                    (dialog, which) -> {
                                                        String selectedProfile =
                                                                profiles.optJSONObject(which)
                                                                        .optString("id", "default");
                                                        dialog.dismiss();
                                                        if (selectedProfile.equals(
                                                                api.getProfile())) return;
                                                        api.setProfile(selectedProfile);
                                                        home = null;
                                                        loadCatalog(true);
                                                    })
                                            .setNegativeButton("Close", null)
                                            .show();
                                });
                    } catch (Exception ignored) {
                        main.post(
                                () -> {
                                    if (!isDestroyed())
                                        Toast.makeText(
                                                        this,
                                                        "Profiles are unavailable",
                                                        Toast.LENGTH_SHORT)
                                                .show();
                                });
                    }
                });
    }

    private void onlineSources(JSONObject item) {
        Toast.makeText(this, "Finding watch options…", Toast.LENGTH_SHORT).show();
        worker.execute(
                () -> {
                    try {
                        JSONObject identity = repository.detail(item);
                        String id = identity.optString("imdb_id");
                        if (id.isEmpty()) throw new IllegalArgumentException("No title identifier");
                        String query =
                                "/api/files/online/sources?imdb_id="
                                        + Uri.encode(id)
                                        + "&kind="
                                        + Uri.encode(identity.optString("kind", "movie"))
                                        + "&season="
                                        + ("series".equals(identity.optString("kind")) ? "1" : "0")
                                        + "&episode="
                                        + ("series".equals(identity.optString("kind")) ? "1" : "0");
                        JSONObject data = api.get(query);
                        JSONArray sources = data.optJSONArray("sources");
                        if (sources == null || sources.length() == 0)
                            throw new IllegalArgumentException("No sources");
                        String[] names = new String[sources.length()];
                        for (int i = 0; i < names.length; i++) {
                            JSONObject source = sources.optJSONObject(i);
                            names[i] =
                                    source.optString("label", "Watch option")
                                            + " "
                                            + source.optString("quality");
                        }
                        main.post(
                                () -> {
                                    if (isDestroyed()) return;
                                    new AlertDialog.Builder(this)
                                            .setTitle("Watch " + item.optString("title"))
                                            .setItems(
                                                    names,
                                                    (dialog, which) -> {
                                                        JSONObject source =
                                                                sources.optJSONObject(which);
                                                        String url =
                                                                source.optString(
                                                                        "url",
                                                                        "/api/files/online/media/"
                                                                                + source.optString(
                                                                                        "id"));
                                                        play(identity, url);
                                                    })
                                            .setNegativeButton("Close", null)
                                            .show();
                                });
                    } catch (Exception ignored) {
                        main.post(
                                () -> {
                                    if (!isDestroyed())
                                        new AlertDialog.Builder(this)
                                                .setTitle("No watch option available")
                                                .setMessage(
                                                        "No compatible online source was found for"
                                                            + " this title. Your downloaded library"
                                                            + " is still available.")
                                                .setPositiveButton("Close", null)
                                                .show();
                                });
                    }
                });
    }

    private void trailer(JSONObject item) {
        JSONArray trailers = item.optJSONArray("trailers");
        JSONObject trailer = trailers == null ? null : trailers.optJSONObject(0);
        if (trailer == null) return;
        Intent intent =
                new Intent(
                        Intent.ACTION_VIEW,
                        Uri.parse(
                                "https://www.youtube.com/watch?v="
                                        + Uri.encode(trailer.optString("id"))));
        try {
            startActivity(intent);
        } catch (Exception ignored) {
            Toast.makeText(
                            this,
                            "Install a compatible YouTube app to watch trailers",
                            Toast.LENGTH_LONG)
                    .show();
        }
    }

    private void configureServer() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        input.setText(server);
        input.setHint("http://server-name:port/");
        AlertDialog dialog =
                new AlertDialog.Builder(this)
                        .setTitle("Autolycus server address")
                        .setView(input)
                        .setPositiveButton("Open", null)
                        .setNegativeButton("Cancel", null)
                        .create();
        dialog.setOnShowListener(
                ignored ->
                        dialog.getButton(AlertDialog.BUTTON_POSITIVE)
                                .setOnClickListener(
                                        view -> {
                                            String value = input.getText().toString().trim();
                                            if (!validServer(value)) {
                                                input.setError(
                                                        "Enter an http:// or https:// address"
                                                                + " without credentials");
                                                return;
                                            }
                                            saveServer(value);
                                            dialog.dismiss();
                                            connect();
                                        }));
        dialog.show();
    }

    private void showLogin() {
        root.removeAllViews();
        home = null;
        LinearLayout columns = new LinearLayout(this);
        columns.setOrientation(LinearLayout.HORIZONTAL);
        root.addView(columns, new FrameLayout.LayoutParams(-1, -1));
        FrameLayout left = new FrameLayout(this);
        columns.addView(left, new LinearLayout.LayoutParams(0, -1, 1));
        ImageView wallpaper = new ImageView(this);
        wallpaper.setScaleType(ImageView.ScaleType.CENTER_CROP);
        left.addView(wallpaper, new FrameLayout.LayoutParams(-1, -1));
        View shade = new View(this);
        shade.setBackground(
                new GradientDrawable(
                        GradientDrawable.Orientation.TOP_BOTTOM,
                        new int[] {0xff08090b, 0xe608090b, 0x1008090b}));
        left.addView(shade, new FrameLayout.LayoutParams(-1, -1));
        LinearLayout introduction = new LinearLayout(this);
        introduction.setOrientation(LinearLayout.VERTICAL);
        introduction.setPadding(dp(40), dp(62), dp(28), 0);
        introduction.addView(text("Autolycus", 19, Color.WHITE, true));
        TextView headline = text("Your next great watch\nstarts here.", 30, Color.WHITE, true);
        LinearLayout.LayoutParams headlineParams = new LinearLayout.LayoutParams(-1, -2);
        headlineParams.topMargin = dp(42);
        introduction.addView(headline, headlineParams);
        TextView explanation =
                text("Your collection, beautifully connected.", 15, 0xffb9bfc9, false);
        LinearLayout.LayoutParams explanationParams = new LinearLayout.LayoutParams(-1, -2);
        explanationParams.topMargin = dp(24);
        introduction.addView(explanation, explanationParams);
        left.addView(introduction, new FrameLayout.LayoutParams(-1, -2));
        FrameLayout right = new FrameLayout(this);
        right.setBackgroundColor(0xff252527);
        columns.addView(right, new LinearLayout.LayoutParams(0, -1, 1));
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(24), dp(20), dp(24), dp(20));
        form.addView(text("Welcome back", 30, Color.WHITE, true));
        TextView hint = text("Please enter your details", 16, 0xffd1d2d4, false);
        hint.setPadding(0, dp(6), 0, dp(26));
        form.addView(hint);
        EditText email = loginField(form, "Email", false);
        EditText password = loginField(form, "Password", true);
        TextView error = text("", 13, 0xffffa9a9, false);
        form.addView(error);
        Button submit = new Button(this);
        submit.setText("Sign in");
        submit.setAllCaps(false);
        submit.setTextSize(16);
        submit.setTextColor(Color.WHITE);
        submit.setBackground(surface(0xff2458d6, 8, 0));
        LinearLayout.LayoutParams submitParams = new LinearLayout.LayoutParams(-1, dp(48));
        submitParams.topMargin = dp(8);
        form.addView(submit, submitParams);
        FrameLayout.LayoutParams formParams = new FrameLayout.LayoutParams(-1, -2, Gravity.CENTER);
        formParams.leftMargin = dp(16);
        formParams.rightMargin = dp(16);
        right.addView(form, formParams);
        for (EditText field : new EditText[] {email, password}) {
            field.setOnClickListener(
                    view -> {
                        form.setTranslationY(-dp(95));
                        int[] location = new int[2];
                        field.getLocationOnScreen(location);
                        Rect bounds =
                                new Rect(
                                        location[0],
                                        location[1],
                                        location[0] + field.getWidth(),
                                        location[1] + field.getHeight());
                        new TvTextEntry(
                                        this,
                                        field == email ? "Enter your email" : "Enter your password",
                                        field == email ? "email" : "password",
                                        field.getText().toString(),
                                        bounds,
                                        value -> field.setText(value),
                                        () -> {
                                            form.setTranslationY(0);
                                            field.requestFocus();
                                        })
                                .show();
                    });
        }
        submit.setOnClickListener(
                view -> {
                    if (email.length() == 0 || password.length() == 0) {
                        error.setText("Enter your email and password.");
                        return;
                    }
                    submit.setEnabled(false);
                    submit.setText("Signing in…");
                    error.setText("");
                    final String username = email.getText().toString().trim();
                    final String secret = password.getText().toString();
                    worker.execute(
                            () -> {
                                try {
                                    JSONObject body =
                                            new JSONObject()
                                                    .put("username", username)
                                                    .put("password", secret);
                                    JSONObject response = api.post("/api/auth/signin", body);
                                    if (!"success".equals(response.optString("msg")))
                                        throw new IllegalStateException("Sign in failed");
                                    main.post(
                                            () -> {
                                                if (!isDestroyed()) {
                                                    password.setText("");
                                                    loadCatalog(true);
                                                }
                                            });
                                } catch (Exception ignored) {
                                    main.post(
                                            () -> {
                                                if (isDestroyed()) return;
                                                error.setText(
                                                        "Unable to sign in. Check your details and"
                                                                + " connection.");
                                                submit.setText("Sign in");
                                                submit.setEnabled(true);
                                            });
                                }
                            });
                });
        email.requestFocus();
        worker.execute(
                () -> {
                    try {
                        HttpURLConnection connection =
                                (HttpURLConnection)
                                        new URL(api.absolute("/images/signin-cinema.jpg"))
                                                .openConnection();
                        connection.setConnectTimeout(8000);
                        connection.setReadTimeout(8000);
                        try {
                            BitmapFactory.Options options = new BitmapFactory.Options();
                            options.inSampleSize = 2;
                            Bitmap image =
                                    BitmapFactory.decodeStream(
                                            connection.getInputStream(), null, options);
                            main.post(
                                    () -> {
                                        if (!isDestroyed() && wallpaper.isAttachedToWindow())
                                            wallpaper.setImageBitmap(image);
                                    });
                        } finally {
                            connection.disconnect();
                        }
                    } catch (Exception ignored) {
                        /* The dark introduction remains complete without artwork. */
                    }
                });
    }

    private EditText loginField(LinearLayout form, String label, boolean password) {
        TextView caption = text(label, 14, 0xffd6d6d8, false);
        caption.setPadding(dp(2), dp(6), 0, dp(6));
        form.addView(caption);
        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setShowSoftInputOnFocus(false);
        field.setCursorVisible(false);
        field.setInputType(
                InputType.TYPE_CLASS_TEXT
                        | (password
                                ? InputType.TYPE_TEXT_VARIATION_PASSWORD
                                : InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS));
        field.setTypeface(Typeface.DEFAULT);
        field.setTextSize(15);
        field.setHint(password ? "Enter your password" : "Enter your email");
        field.setTextColor(Color.WHITE);
        field.setHintTextColor(0xff8a8c91);
        field.setPadding(dp(16), 0, dp(16), 0);
        field.setBackground(surface(Color.BLACK, 8, 0xff454850));
        field.setOnFocusChangeListener(
                (view, focused) ->
                        field.setBackground(
                                surface(Color.BLACK, 8, focused ? 0xffaab6c8 : 0xff454850)));
        form.addView(field, new LinearLayout.LayoutParams(-1, dp(48)));
        return field;
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextColor(color);
        view.setTextSize(size);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private GradientDrawable surface(int color, int radius, int stroke) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radius));
        if (stroke != 0) drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    public void onBackPressed() {
        if (home != null && home.onBack()) return;
        super.onBackPressed();
    }

    @Override
    protected void onResume() {
        super.onResume();
        immersive();
        if (returnFromPlayer && repository != null) {
            returnFromPlayer = false;
            loadCatalog(false);
        }
    }

    @Override
    protected void onDestroy() {
        generation++;
        worker.shutdownNow();
        super.onDestroy();
    }
}
