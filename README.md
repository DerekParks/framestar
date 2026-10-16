# framestar

A WeatherStar 4000 style kiosk for a hacked Android photo frame. It cycles through these slides:

- **calendar**: the next N days of chosen iCal feeds, with its own title, scrolling if it overflows
- **ws4kp**: a [WeatherStar 4000+](https://github.com/netbymatt/ws4kp) run for a location, labelled with the city
- **tempest**: current conditions and a 5-day forecast from a WeatherFlow Tempest station
- **photos**: a random handful from an Immich share link, composed on the server over a blurred fill
- **radar**: an animated hour of NEXRAD composite radar, rendered on the server into a single JPEG per frame
- **cams**: still frames from webcams (direct images, YouTube live, camstreamer embeds)
- **mountain**: NRCS SNOTEL temperature, snow depth and new snow for a list of sites

From `quiet_hours` start to end the screen goes dark; otherwise Android's auto-brightness handles dimming.
The kiosk sets an alarm for the end of quiet hours, so the frame wakes even after Android has suspended.

A crawl along the bottom shows the Tempest reading and upcoming events.

```
frame (Android WebView) ──http──▶ framestar :8000 ──▶ Google iCal, Tempest, Immich, IEM radar, Esri basemap
                         └─http──▶ ws4kp     :8080 ──▶ api.weather.gov and friends (proxied + cached)
```

Everything the frame loads is plain HTTP on the LAN. The PF1007L has no ISRG Root X1 certificate, so
any Let's Encrypt site fails in its WebView. The server makes all the HTTPS calls instead.

## Run it

```sh
cp config.example.yaml config.yaml   # fill in calendars, tempest token, immich link
docker compose up -d --build
open http://localhost:8000/
```

`FRAMESTAR_PORT` and `WS4KP_PORT` change the host ports. If you change the ws4kp port, change
`ws4kp_url` in `config.yaml` to match.

Debug params: `?start=3` starts at slide 3, and `?hold` stays on the first slide shown.

### Getting the secrets

| Thing | Where |
| --- | --- |
| Google Calendar | Calendar settings → *Integrate calendar* → **Secret address in iCal format**. You don't need to make the calendar public. |
| Tempest | <https://tempestwx.com/settings/tokens> → create a token. The station ID is in your station's URL. |
| Immich | Album → Share → *Create link*. Paste the whole `/share/<key>` or `/s/<slug>` URL, plus `password:` if the link has one. |

## The frame (Aimor = Allwinner PF1007L)

Background is in Wes Bos's [PF1007L notes](https://github.com/wesbos/photo-frame-dashboard/blob/main/docs/pf1007l-start-here.md).
The AiMOR home app [runs root shell commands sent by its vendor server](https://github.com/wesbos/photo-frame-dashboard/blob/main/docs/aimor-remote-root-shell.md),
so it gets disabled, not merely replaced. This unit (firmware `...PF1007L-321-OS-AIMOR.0.20260410`)
ships with root ADB over USB, so no boot patching is needed.

```sh
adb shell pm disable com.efercro.os.aimor     # vendor launcher + remote root shell
adb shell pm disable com.yhk.qeota            # vendor OTA updater
adb shell pm disable com.DeviceTest           # system-uid app that can re-enable any package
device/webview-swap.sh device/downloads/webview.apk   # stock WebView 44 -> 106 (--rollback undoes)
JAVA_HOME=<jdk17> FRAMESTAR_URL=http://10.0.0.117:8000/ kiosk/build.sh
adb install -r kiosk/build/framestar-kiosk.apk
```

WebView 106 is the LineageOS prebuilt pinned by SHA-256 in `device/webview-swap.sh`:
`https://raw.githubusercontent.com/LineageOS/android_external_chromium-webview_prebuilt_arm/4b0ae494a7dd/webview.apk`.
Android 6 does not extract a system app's native libraries, so the script installs them beside the APK.

`kiosk/` is a home-screen WebView app, so it starts on boot. It persists the last URL it was sent:

```sh
adb shell am start -a android.intent.action.VIEW -d http://10.0.0.117:8000/ -n icu.snafu.framestar/.KioskActivity
```

Holding three fingers still for three seconds opens Android Settings. `--ez debug true` on that
`am start` enables WebView remote debugging until the next launch. During quiet hours the kiosk
drops its keep-awake flag so Android's screen timeout turns the panel off; the frame ships with
that timeout set to never, so set one: `adb shell settings put system screen_off_timeout 60000`. `kiosk/build.sh` needs build-tools 34,
platform 34 and a JDK 17 `javac`: build-tools 34's `d8` crashes on JDK 21 class files.

For testing against a desktop over USB, `adb reverse tcp:8000 tcp:8000 && adb reverse tcp:8080 tcp:8080`
and point the kiosk at `http://127.0.0.1:8000/`.

framestar formats its own times in the configured `timezone`, but ws4kp uses the device clock:
`adb shell setprop persist.sys.timezone America/Denver`.

The front end is plain ES2020 and CSS with no build step. It avoids what WebView 106 lacks:
`:has()`, CSS nesting, `color-mix()`, `oklch()` and 4/8-digit hex colours.

## Deployment

Production runs on `aquabats` (`~/framestar`, ports 8000/8080), on the same LAN as the frame.
`config.yaml` is not in git; copy it alongside the repo. To update: `rsync` or `git pull` there,
then `docker compose up -d --build`.

The kiosk picks its server by Wi-Fi network name, checked at launch and on every network change.
Build the map in with `FRAMESTAR_SSID_URLS="BoomerSooner=http://192.168.1.25:8090/;irish=http://10.0.0.117:8000/"`
or replace it on the device without a rebuild:

```sh
adb shell am start -n icu.snafu.framestar/.KioskActivity --es ssid_urls 'irish=http://10.0.0.117:8000/'
```

On an unmapped network it keeps its fallback URL (`FRAMESTAR_URL`, or the last VIEW intent).
To repoint it by hand from anywhere through the jump host:

```sh
device/repoint-frame.sh                      # defaults: JUMP=aquabats SUBNET=10.0.0 URL=http://10.0.0.117:8000/
```

It scans the subnet for ADB, tunnels to each answer over SSH, confirms `ro.es_frame.product=PF1007L`,
and sends the URL. The frame's ADB takes one network connection at a time, so the script drops any
existing ones first.

## Gotchas

- ws4kp remembers enabled screens in localStorage. framestar pins every screen in each link
  (`WS4KP_DISPLAYS` in `app.py`), so turn screens off with `ws4kp_defaults` or a slide's `params`.
- A ws4kp city slot is about 2 minutes; the long-scrolling hourly screen alone would fill it.
- The kiosk renders in software: the frame's Mali-400 fails some WebView 106 GPU shaders.
- YAML reads an unquoted `22:00` as the number 1320, so quote clock times.
- Calendar text is stripped of emoji; Star4000 has none and the fallback blanked the slide.
- Never `stop adbd` from `adb shell` on the frame; use `adb tcpip 5555`. Its IP changes every boot.

## Develop

```sh
uv sync
uv run pytest
FRAMESTAR_CONFIG=config.yaml uv run framestar --port 8000
```

Fonts and weather icons in `framestar/static/` come from ws4kp (MIT, see `LICENSE-ws4kp`).
