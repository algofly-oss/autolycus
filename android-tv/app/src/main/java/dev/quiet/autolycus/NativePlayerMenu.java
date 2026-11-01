package dev.quiet.autolycus;

import android.app.Dialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.function.IntConsumer;

/** Compact native settings popover matching the cinema player's dark surface. */
final class NativePlayerMenu {
    private NativePlayerMenu() {}

    static Dialog show(
            Context context,
            String heading,
            String[] choices,
            IntConsumer selected,
            Runnable dismissed,
            Runnable back,
            int selectedRow) {
        Dialog dialog = new Dialog(context);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout panel = new LinearLayout(context);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(context, 8), dp(context, 6), dp(context, 8), dp(context, 8));
        GradientDrawable background = new GradientDrawable();
        background.setColor(0xf51b1d21);
        background.setCornerRadius(dp(context, 10));
        background.setStroke(dp(context, 1), 0x18ffffff);
        panel.setBackground(background);
        LinearLayout header = new LinearLayout(context);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = new TextView(context);
        title.setText(heading);
        title.setTextSize(15);
        title.setTextColor(Color.WHITE);
        title.setTypeface(null, Typeface.BOLD);
        title.setPadding(dp(context, 12), 0, 0, 0);
        header.addView(title, new LinearLayout.LayoutParams(0, dp(context, 40), 1));
        title.setGravity(Gravity.CENTER_VERTICAL);
        panel.addView(header);
        ViewDivider.add(context, panel);
        ScrollView scroll = new ScrollView(context);
        scroll.setFillViewport(false);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout rows = new LinearLayout(context);
        rows.setOrientation(LinearLayout.VERTICAL);
        rows.setPadding(0, dp(context, 4), 0, 0);
        TextView first = null;
        for (int i = 0; i < choices.length; i++) {
            final int index = i;
            TextView row = new TextView(context);
            row.setText(choices[i]);
            row.setTextSize(14);
            row.setTextColor(0xffe1e3e8);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(context, 12), dp(context, 10), dp(context, 12), dp(context, 10));
            row.setMinHeight(dp(context, 44));
            row.setFocusable(true);
            row.setClickable(true);
            row.setOnFocusChangeListener(
                    (v, focused) -> {
                        GradientDrawable shape = new GradientDrawable();
                        shape.setCornerRadius(dp(context, 6));
                        shape.setColor(focused ? 0x25ffffff : Color.TRANSPARENT);
                        v.setBackground(shape);
                    });
            row.setOnClickListener(
                    v -> {
                        dialog.dismiss();
                        selected.accept(index);
                    });
            rows.addView(row, new LinearLayout.LayoutParams(-1, -2));
            if (first == null || i == selectedRow) first = row;
        }
        scroll.addView(rows);
        int available = context.getResources().getDisplayMetrics().heightPixels - dp(context, 190);
        int height =
                Math.min(
                        dp(context, Math.max(44, choices.length * 44 + 4)),
                        Math.max(dp(context, 90), available));
        panel.addView(scroll, new LinearLayout.LayoutParams(-1, height));
        dialog.setContentView(panel);
        Window window = dialog.getWindow();
        window.setBackgroundDrawableResource(android.R.color.transparent);
        window.setGravity(Gravity.BOTTOM | Gravity.RIGHT);
        WindowManager.LayoutParams position = window.getAttributes();
        position.x = dp(context, 28);
        position.y = dp(context, 90);
        window.setAttributes(position);
        window.setLayout(dp(context, 300), -2);
        window.clearFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
        window.setWindowAnimations(0);
        dialog.setOnDismissListener(ignored -> dismissed.run());
        dialog.setOnCancelListener(
                ignored -> {
                    if (back != null) back.run();
                });
        dialog.show();
        if (first != null) first.requestFocus();
        return dialog;
    }

    private static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    private static final class ViewDivider {
        static void add(Context context, LinearLayout panel) {
            android.view.View line = new android.view.View(context);
            line.setBackgroundColor(0x14ffffff);
            panel.addView(line, new LinearLayout.LayoutParams(-1, dp(context, 1)));
        }
    }
}
