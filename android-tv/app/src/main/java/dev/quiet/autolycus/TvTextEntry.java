package dev.quiet.autolycus;

import android.app.Dialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.InputType;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.LinearLayout;

import java.util.function.Consumer;

/** Native TV editor; credentials remain in memory and the site's own form. */
final class TvTextEntry extends Dialog {
    TvTextEntry(
            Context context,
            String label,
            String type,
            String value,
            Rect bounds,
            Consumer<String> save,
            Runnable closed) {
        super(context);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout panel = new LinearLayout(context);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(0, 0, 0, 0);
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.BLACK);
        background.setCornerRadius(dp(8));
        panel.setBackground(background);
        EditText input =
                new EditText(context) {
                    @Override
                    public boolean onKeyPreIme(int keyCode, KeyEvent event) {
                        if (keyCode == KeyEvent.KEYCODE_BACK) {
                            if (event.getAction() == KeyEvent.ACTION_UP) {
                                ((InputMethodManager)
                                                context.getSystemService(
                                                        Context.INPUT_METHOD_SERVICE))
                                        .hideSoftInputFromWindow(getWindowToken(), 0);
                                TvTextEntry.this.dismiss();
                            }
                            return true;
                        }
                        return super.onKeyPreIme(keyCode, event);
                    }
                };
        input.setBackgroundColor(Color.TRANSPARENT);
        input.setHint(label);
        input.setHintTextColor(0xffa9adb5);
        input.setContentDescription(label);
        input.setSingleLine(true);
        input.setTextSize(14);
        input.setPadding(dp(12), 0, dp(12), 0);
        input.setTextColor(Color.WHITE);
        input.setInputType(
                InputType.TYPE_CLASS_TEXT
                        | ("password".equals(type)
                                ? InputType.TYPE_TEXT_VARIATION_PASSWORD
                                : "email".equals(type)
                                        ? InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
                                        : InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS));
        input.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        input.setTypeface(Typeface.DEFAULT);
        input.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);
        input.setText(value);
        input.setSelection(input.length());
        panel.addView(input, new LinearLayout.LayoutParams(-1, bounds.height()));
        Runnable commit =
                () -> {
                    ((InputMethodManager) context.getSystemService(Context.INPUT_METHOD_SERVICE))
                            .hideSoftInputFromWindow(input.getWindowToken(), 0);
                    dismiss();
                };
        // Back dismisses the editor without discarding what the owner typed.
        setOnDismissListener(
                ignored -> {
                    save.accept(input.getText().toString());
                    closed.run();
                });
        input.setOnEditorActionListener(
                (view, action, event) -> {
                    if (action == EditorInfo.IME_ACTION_DONE
                            || action == EditorInfo.IME_ACTION_NEXT) {
                        commit.run();
                        return true;
                    }
                    return false;
                });
        setContentView(panel);
        Window window = getWindow();
        window.setBackgroundDrawableResource(android.R.color.transparent);
        window.setGravity(Gravity.TOP | Gravity.LEFT);
        WindowManager.LayoutParams params = window.getAttributes();
        params.x = bounds.left;
        params.y = bounds.top;
        window.setAttributes(params);
        window.setLayout(bounds.width(), bounds.height());
        window.clearFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_PAN);
        window.setWindowAnimations(0);
        input.requestFocus();
        setOnShowListener(
                ignored ->
                        input.post(
                                () ->
                                        ((InputMethodManager)
                                                        context.getSystemService(
                                                                Context.INPUT_METHOD_SERVICE))
                                                .showSoftInput(
                                                        input, InputMethodManager.SHOW_IMPLICIT)));
    }

    private int dp(int value) {
        return Math.round(value * getContext().getResources().getDisplayMetrics().density);
    }
}
