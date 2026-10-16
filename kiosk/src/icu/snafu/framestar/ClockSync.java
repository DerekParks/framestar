package icu.snafu.framestar;

import android.Manifest;
import android.content.ContentResolver;
import android.content.Context;
import android.content.pm.PackageManager;
import android.provider.Settings;
import android.util.Log;

/** The frame has no RTC battery: it boots at the epoch, and Android stops retrying NTP for a day after three misses. */
final class ClockSync {
  private static final String TAG = "Framestar";
  private static final long PLAUSIBLE_MS = 1_767_225_600_000L; // 2026-01-01T00:00Z

  private ClockSync() {}

  static boolean clockUnset() {
    return System.currentTimeMillis() < PLAUSIBLE_MS;
  }

  /** Re-enabling automatic time makes the time service fetch NTP immediately. */
  static void forceNtpFetch(Context context) {
    if (context.checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS)
        != PackageManager.PERMISSION_GRANTED) {
      Log.w(TAG, "clock unset; grant WRITE_SECURE_SETTINGS so the kiosk can force an NTP fetch");
      return;
    }
    ContentResolver resolver = context.getContentResolver();
    if (Settings.Global.getInt(resolver, Settings.Global.AUTO_TIME, 0) == 0) {
      Log.w(TAG, "clock unset and automatic time is off");
      return;
    }
    Log.i(TAG, "clock unset; forcing an NTP fetch");
    Settings.Global.putInt(resolver, Settings.Global.AUTO_TIME, 0);
    Settings.Global.putInt(resolver, Settings.Global.AUTO_TIME, 1);
  }
}
