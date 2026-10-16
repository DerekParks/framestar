package icu.snafu.framestar;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.PowerManager;
import android.util.Log;

/** Fires when quiet hours end: turns the panel on and brings the kiosk back, even from deep sleep. */
public class WakeReceiver extends BroadcastReceiver {
  static final String ACTION_WAKE = "icu.snafu.framestar.WAKE";
  private static final String TAG = "Framestar";
  private static final long WAKE_MS = 5_000;

  @Override
  public void onReceive(Context context, Intent intent) {
    Log.i(TAG, "quiet hours over; waking");
    wakeScreen(context);
    context.startActivity(new Intent(context, KioskActivity.class)
        .setAction(ACTION_WAKE)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
  }

  static void schedule(Context context, long wakeAtMs) {
    alarms(context).setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, wakeAtMs, pending(context));
    Log.i(TAG, "wake scheduled in " + (wakeAtMs - System.currentTimeMillis()) / 60_000 + " min");
  }

  static void cancel(Context context) {
    alarms(context).cancel(pending(context));
  }

  @SuppressWarnings("deprecation")
  static void wakeScreen(Context context) {
    PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
    pm.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP, TAG + ":wake")
        .acquire(WAKE_MS);
  }

  private static AlarmManager alarms(Context context) {
    return (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
  }

  private static PendingIntent pending(Context context) {
    return PendingIntent.getBroadcast(context, 0, new Intent(context, WakeReceiver.class),
        PendingIntent.FLAG_UPDATE_CURRENT);
  }
}
