package icu.snafu.framestar;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * Full-screen home app that shows the framestar page.
 *
 * <p>Repoint it without rebuilding (the URL persists):
 * {@code adb shell am start -a android.intent.action.VIEW -d http://10.0.0.117:8000/ -n icu.snafu.framestar/.KioskActivity}
 *
 * <p>The page can switch the backlight with {@code FramestarKiosk.setDisplayOn(bool)}.
 *
 * <p>Remote WebView debugging only while launched with {@code --ez debug true}.
 * Holding three fingers still for three seconds opens Android Settings.
 */
public class KioskActivity extends Activity {
  private static final String TAG = "Framestar";
  private static final String PREFS = "kiosk";
  private static final String PREF_URL = "url";
  private static final long RETRY_MS = 15_000;
  private static final long ESCAPE_HOLD_MS = 3_000;
  private static final float ESCAPE_SLOP_PX = 80;

  private final Handler handler = new Handler(Looper.getMainLooper());
  private final Runnable retry = () -> load(url());
  private final Runnable escape = this::openSettings;
  private final float[] escapeX = new float[3];
  private final float[] escapeY = new float[3];
  private boolean escapeArmed;
  private WebView web;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON | WindowManager.LayoutParams.FLAG_FULLSCREEN);
    web = new WebView(this);
    WebSettings settings = web.getSettings();
    settings.setJavaScriptEnabled(true);
    settings.setDomStorageEnabled(true);
    settings.setMediaPlaybackRequiresUserGesture(false);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
    web.setBackgroundColor(0xFF000000);
    web.setWebViewClient(new RetryingClient());
    web.addJavascriptInterface(new Bridge(), "FramestarKiosk");
    setContentView(web);
    handleIntent(getIntent());
  }

  @Override
  protected void onNewIntent(Intent intent) {
    super.onNewIntent(intent);
    handleIntent(intent);
  }

  private void handleIntent(Intent intent) {
    WebView.setWebContentsDebuggingEnabled(intent != null && intent.getBooleanExtra("debug", false));
    Uri data = intent == null ? null : intent.getData();
    if (data != null) {
      getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(PREF_URL, data.toString()).apply();
    }
    load(url());
  }

  private String url() {
    SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
    return prefs.getString(PREF_URL, getString(R.string.default_url));
  }

  private void load(String url) {
    handler.removeCallbacks(retry);
    Log.i(TAG, "loading " + url);
    web.loadUrl(url);
  }

  private final class Bridge {
    @JavascriptInterface
    public void setDisplayOn(boolean on) {
      runOnUiThread(() -> {
        WindowManager.LayoutParams attrs = getWindow().getAttributes();
        attrs.screenBrightness = on
            ? WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE
            : WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_OFF;
        getWindow().setAttributes(attrs);
        Log.i(TAG, "display " + (on ? "on" : "off"));
      });
    }
  }

  private final class RetryingClient extends WebViewClient {
    @Override
    public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
      if (!request.isForMainFrame()) return;
      Log.w(TAG, "load failed: " + error.getDescription() + "; retrying");
      view.loadData("<body style='background:#000'></body>", "text/html", null);
      handler.removeCallbacks(retry);
      handler.postDelayed(retry, RETRY_MS);
    }
  }

  @Override
  public boolean dispatchTouchEvent(MotionEvent e) {
    switch (e.getActionMasked()) {
      case MotionEvent.ACTION_POINTER_DOWN:
        if (e.getPointerCount() == 3) {
          for (int i = 0; i < 3; i++) {
            escapeX[i] = e.getX(i);
            escapeY[i] = e.getY(i);
          }
          escapeArmed = true;
          handler.postDelayed(escape, ESCAPE_HOLD_MS);
        } else {
          disarmEscape();
        }
        break;
      case MotionEvent.ACTION_MOVE:
        if (escapeArmed && movedTooFar(e)) disarmEscape();
        break;
      case MotionEvent.ACTION_POINTER_UP:
      case MotionEvent.ACTION_UP:
      case MotionEvent.ACTION_CANCEL:
        disarmEscape();
        break;
      default:
        break;
    }
    return super.dispatchTouchEvent(e);
  }

  private boolean movedTooFar(MotionEvent e) {
    for (int i = 0; i < Math.min(3, e.getPointerCount()); i++) {
      if (Math.hypot(e.getX(i) - escapeX[i], e.getY(i) - escapeY[i]) > ESCAPE_SLOP_PX) return true;
    }
    return false;
  }

  private void disarmEscape() {
    escapeArmed = false;
    handler.removeCallbacks(escape);
  }

  private void openSettings() {
    escapeArmed = false;
    startActivity(new Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
  }

  @Override
  public void onWindowFocusChanged(boolean hasFocus) {
    super.onWindowFocusChanged(hasFocus);
    if (hasFocus) {
      getWindow().getDecorView().setSystemUiVisibility(
          View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
              | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
              | View.SYSTEM_UI_FLAG_FULLSCREEN
              | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
              | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
              | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }
  }

  @Override
  public void onBackPressed() {}
}
