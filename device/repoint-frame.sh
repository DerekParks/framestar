#!/usr/bin/env bash
# Point the frame's kiosk at a framestar URL, reaching the frame through a jump host on its LAN.
set -euo pipefail

JUMP=${JUMP:-aquabats}
SUBNET=${SUBNET:-10.0.0}
URL=${1:-http://10.0.0.117:8000/}
LOCAL_PORT=${LOCAL_PORT:-15555}

die() { echo "ABORT: $*" >&2; exit 1; }

echo "scanning $SUBNET.0/24 from $JUMP for ADB on 5555..."
mapfile -t candidates < <(ssh "$JUMP" "for i in \$(seq 1 254); do (timeout 1 bash -c '</dev/tcp/$SUBNET.'\$i'/5555' 2>/dev/null && echo $SUBNET.\$i) & done; wait")
(( ${#candidates[@]} )) || die "nothing on $SUBNET.0/24 answers on 5555; is the frame on Wi-Fi?"

adb disconnect >/dev/null 2>&1 || true

tunnel=""
cleanup() {
  adb disconnect "localhost:$LOCAL_PORT" >/dev/null 2>&1 || true
  [[ -n $tunnel ]] && kill "$tunnel" 2>/dev/null || true
}
trap cleanup EXIT

for ip in "${candidates[@]}"; do
  ssh -N -L "$LOCAL_PORT:$ip:5555" "$JUMP" & tunnel=$!
  sleep 2
  adb connect "localhost:$LOCAL_PORT" >/dev/null 2>&1 || true
  sleep 2
  product=$(adb -s "localhost:$LOCAL_PORT" shell getprop ro.es_frame.product 2>/dev/null | tr -d '\r' || true)
  if [[ $product == PF1007L ]]; then
    echo "frame found at $ip"
    adb -s "localhost:$LOCAL_PORT" shell "am start -a android.intent.action.VIEW -d '$URL' -n icu.snafu.framestar/.KioskActivity" | tr -d '\r'
    sleep 5
    adb -s "localhost:$LOCAL_PORT" shell 'logcat -d -s Framestar | tail -2' | tr -d '\r'
    exit 0
  fi
  echo "$ip is not the frame (${product:-no answer}); skipping"
  adb disconnect "localhost:$LOCAL_PORT" >/dev/null 2>&1 || true
  kill "$tunnel" 2>/dev/null || true
  tunnel=""
done
die "no PF1007L among: ${candidates[*]}"
