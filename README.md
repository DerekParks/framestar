# framestar

A WeatherStar 4000 style kiosk for a hacked Android photo frame. It cycles through these slides:

- **calendar**: the next N days of one or more Google Calendars (iCal feeds), scrolling if they overflow
- **ws4kp**: a full [WeatherStar 4000+](https://github.com/netbymatt/ws4kp) run for a location (Denver, Fraser, Norman, ...)
- **tempest**: current conditions and a 5-day forecast from a WeatherFlow Tempest station
- **photos**: a random handful from an Immich share link, composed on the server over a blurred fill
- **radar**: an animated hour of NEXRAD composite radar, rendered on the server into a single JPEG per frame

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

Follow Wes Bos's [PF1007L guide](https://github.com/wesbos/photo-frame-dashboard/blob/main/docs/pf1007l-start-here.md).
Read [the AiMOR remote root shell writeup](https://github.com/wesbos/photo-frame-dashboard/blob/main/docs/aimor-remote-root-shell.md)
**before** the frame touches Wi-Fi. Then:

1. Install WebView 106 and the kiosk app from that repo. Set its `DEFAULT_URL` to `http://<server>:8000/`.
2. Set the time zone, which ships as New York: `adb shell setprop persist.sys.timezone America/Denver`.
   framestar's own slides format times in `timezone` from the config, but ws4kp uses the device clock.
3. The page is designed for 1280×800, the panel's native size, and scales to any other size.

The front end is plain ES2020 and CSS with no build step. It avoids what WebView 106 lacks:
`:has()`, CSS nesting, `color-mix()`, `oklch()` and 4/8-digit hex colours.

## Develop

```sh
uv sync
uv run pytest
FRAMESTAR_CONFIG=config.yaml uv run framestar --port 8000
```

Fonts and weather icons in `framestar/static/` come from ws4kp (MIT, see `LICENSE-ws4kp`).
