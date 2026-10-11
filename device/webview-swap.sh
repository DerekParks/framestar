#!/usr/bin/env bash
# Replace the PF1007L's stock WebView 44 with WebView 106, keeping the stock tree for rollback.
# Usage: device/webview-swap.sh <webview.apk>        install
#        device/webview-swap.sh --rollback           restore the stock tree
set -euo pipefail

WEBVIEW_SHA256=e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580
LIVE=/system/app/webview
STOCK=/system/framestar-stock-webview
NEW=/system/framestar-new-webview
STAGE=/data/local/tmp/framestar-webview

adb_sh() { adb -d shell "$@" | tr -d '\r'; }
die() { echo "ABORT: $*" >&2; exit 1; }
remote_sha() { adb -d exec-out "cat '$1'" | sha256sum | cut -d' ' -f1; }

rollback() {
  [[ $(adb_sh "[ -d $STOCK ] && echo yes") == yes ]] || die "no stock tree at $STOCK"
  adb_sh "mount -o remount,rw /system && mv $LIVE $NEW.failed && mv $STOCK $LIVE && sync && mount -o remount,ro /system"
  echo "restored stock WebView; reboot to apply"
}

install() {
  local apk=$1 work
  echo "$WEBVIEW_SHA256  $apk" | sha256sum -c --quiet || die "APK hash mismatch"
  [[ $(adb_sh id) == uid=0* ]] || die "adb shell is not root"
  for path in $STOCK $NEW $STAGE; do
    [[ $(adb_sh "[ -e $path ] && echo exists") != exists ]] || die "$path already exists; refusing to overwrite"
  done
  local free_kb
  free_kb=$(adb_sh "toybox df -k /system" | tail -1 | tr -s ' ' | cut -d' ' -f4)
  (( free_kb > 300000 )) || die "only ${free_kb} KiB free on /system"

  work=$(mktemp -d)
  trap 'rm -rf "$work"' RETURN
  unzip -q -o "$apk" 'lib/armeabi-v7a/*.so' -d "$work"
  cp "$apk" "$work/webview.apk"

  adb -d push "$work/webview.apk" "$STAGE/webview.apk" >/dev/null
  adb -d push "$work/lib/armeabi-v7a/." "$STAGE/lib/arm/" >/dev/null

  adb_sh "mount -o remount,rw /system"
  adb_sh "mkdir -p $NEW/lib/arm && cp $STAGE/webview.apk $NEW/ && cp $STAGE/lib/arm/*.so $NEW/lib/arm/ \
    && chown -R root:root $NEW && chmod 755 $NEW $NEW/lib $NEW/lib/arm && chmod 644 $NEW/webview.apk $NEW/lib/arm/*.so && sync"

  verify_tree "$work" "$NEW"
  adb_sh "mv $LIVE $STOCK && mv $NEW $LIVE && sync"
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
