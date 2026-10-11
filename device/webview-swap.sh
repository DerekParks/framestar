#!/usr/bin/env bash
# Replace the PF1007L's stock WebView 44 with WebView 106, keeping the stock tree for rollback.
set -euo pipefail

WEBVIEW_SHA256=e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580
LIVE=/system/app/webview
STOCK=/system/framestar-stock-webview
NEW=/system/framestar-new-webview
STAGE=/data/local/tmp/framestar-webview
BACKUP_DIR="$(dirname "$0")/backups"

work=""
cleanup() {
  [[ -n $work ]] && rm -rf "$work"
  adb -d shell "rm -rf $STAGE; mount -o remount,ro /system" >/dev/null 2>&1 || true
}
trap cleanup EXIT

adb_sh() { adb -d shell "$@" | tr -d '\r'; }
die() { echo "ABORT: $*" >&2; exit 1; }
remote_sha() { adb -d exec-out "cat '$1'" | sha256sum | cut -d' ' -f1; }
remote_test() { [[ $(adb_sh "$1 && echo yes") == yes ]]; }
require_root() { [[ $(adb_sh id) == uid=0* ]] || die "adb shell is not root"; }

rollback() {
  require_root
  remote_test "[ -d $STOCK ]" || die "no stock tree at $STOCK"
  remote_test "[ -f $STOCK/webview.apk ] && [ -d $STOCK/oat ]" || die "$STOCK is not a complete stock tree"
  adb_sh "mount -o remount,rw /system"
  remote_test "[ -w /system ]" || die "could not remount /system read-write"
  adb_sh "rm -rf $NEW.failed; [ -e $LIVE ] && mv $LIVE $NEW.failed; mv $STOCK $LIVE && sync"
  remote_test "[ -f $LIVE/webview.apk ] && [ -d $LIVE/oat ] && ! [ -e $STOCK ]" || die "rollback left $LIVE incomplete; inspect $LIVE, $STOCK and $NEW.failed"
  adb_sh "mount -o remount,ro /system"
  echo "restored stock WebView ($(remote_sha "$LIVE/webview.apk")); reboot to apply"
}

install() {
  local apk=$1 backup
  echo "$WEBVIEW_SHA256  $apk" | sha256sum -c --quiet || die "APK hash mismatch"
  require_root
  for path in $STOCK $NEW $STAGE; do
    remote_test "! [ -e $path ]" || die "$path already exists; refusing to overwrite"
  done
  remote_test "[ -f $LIVE/webview.apk ]" || die "no WebView at $LIVE"
  local free_kb
  free_kb=$(adb_sh "toybox df -k /system" | tail -1 | tr -s ' ' | cut -d' ' -f4)
  (( free_kb > 300000 )) || die "only ${free_kb} KiB free on /system"

  backup="$BACKUP_DIR/stock-webview-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$backup"
  adb -d pull "$LIVE" "$backup" >/dev/null
  [[ -f "$backup/webview/webview.apk" ]] || die "pulling $LIVE to $backup failed"
  echo "stock tree pulled to $backup"

  work=$(mktemp -d)
  unzip -q -o "$apk" 'lib/armeabi-v7a/*.so' -d "$work"
  cp "$apk" "$work/webview.apk"

  adb -d push "$work/webview.apk" "$STAGE/webview.apk" >/dev/null
  adb -d push "$work/lib/armeabi-v7a/." "$STAGE/lib/arm/" >/dev/null

  adb_sh "mount -o remount,rw /system"
  remote_test "[ -w /system ]" || die "could not remount /system read-write"
  adb_sh "mkdir -p $NEW/lib/arm && cp $STAGE/webview.apk $NEW/ && cp $STAGE/lib/arm/*.so $NEW/lib/arm/ \
    && chown -R root:root $NEW && chmod 755 $NEW $NEW/lib $NEW/lib/arm && chmod 644 $NEW/webview.apk $NEW/lib/arm/*.so && sync"

  verify_tree "$work" "$NEW"
  adb_sh "mv $LIVE $STOCK && mv $NEW $LIVE && sync"
  remote_test "[ -d $STOCK ] && ! [ -e $NEW ]" || die "swap left $LIVE/$STOCK/$NEW in an unexpected state; inspect before retrying"
  verify_tree "$work" "$LIVE"
  adb_sh "sync && mount -o remount,ro /system && rm -rf $STAGE"
  echo "WebView 106 in place, stock tree kept at $STOCK. Reboot, then check dumpsys package com.android.webview."
}

verify_tree() {
  local work=$1 tree=$2 f
  [[ $(remote_sha "$tree/webview.apk") == $(sha256sum "$work/webview.apk" | cut -d' ' -f1) ]] || die "$tree/webview.apk differs"
  for f in "$work"/lib/armeabi-v7a/*.so; do
    [[ $(remote_sha "$tree/lib/arm/$(basename "$f")") == $(sha256sum "$f" | cut -d' ' -f1) ]] || die "$tree/lib/arm/$(basename "$f") differs"
  done
  adb_sh "ls -lR $tree" | grep -E '^[-d]' | grep -vE '^(-rw-r--r--|drwxr-xr-x) root +root ' && die "bad owner or mode in $tree"
  echo "verified $tree"
}

case "${1:-}" in
  --rollback) rollback ;;
  "") die "usage: $0 <webview.apk> | --rollback" ;;
  *) install "$1" ;;
esac
