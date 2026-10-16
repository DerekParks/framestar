const STAGE_W = 1280;
const STAGE_H = 800;
const PREPARE_LEAD_MS = 8000;
const TRANSITION_MS = 900;
const CRAWL_PX_PER_SEC = 110;
const CRAWL_REFRESH_MS = 5 * 60 * 1000;
const RELOAD_AFTER_MS = 6 * 60 * 60 * 1000;
const RADAR_STEP_MS = 450;
const RADAR_HOLD_MS = 2000;
const QUIET_POLL_MS = 30 * 1000;

const $ = (sel) => document.querySelector(sel);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k === 'style') node.style.cssText = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) {
    if (child == null) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function getJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`image failed: ${src}`));
    img.src = src;
  });
}

function fitStage() {
  const scale = Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H);
  const stage = $('#stage');
  stage.style.transform = `scale(${scale})`;
  stage.style.left = `${(window.innerWidth - STAGE_W * scale) / 2}px`;
  stage.style.top = `${(window.innerHeight - STAGE_H * scale) / 2}px`;
}

class Formatters {
  constructor(timeZone) {
    this.timeZone = timeZone;
    this.time = new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', minute: '2-digit' });
    this.clockTime = new Intl.DateTimeFormat('en-US', { timeZone, hour: 'numeric', minute: '2-digit', second: '2-digit' });
    this.clockDate = new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'short', month: 'short', day: 'numeric' });
    this.dayHead = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'long', month: 'short', day: 'numeric' });
    this.weekday = new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'short' });
    this.monthYear = new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' });
  }

  calendarDay(isoDate) {
    return this.dayHead.format(new Date(`${isoDate}T12:00:00Z`)).toUpperCase();
  }
}

function eventWhen(event, fmt) {
  if (event.all_day) return 'ALL DAY';
  if (event.continued) return `TIL ${fmt.time.format(new Date(event.end))}`;
  return fmt.time.format(new Date(event.start));
}

class CalendarSlide {
  constructor(cfg, ctx) { this.cfg = cfg; this.ctx = ctx; }

  titles() { return this.cfg.title; }

  async prepare(root) {
    const query = (this.cfg.calendars || []).map((n) => `names=${encodeURIComponent(n)}`).join('&');
    const data = await getJson(`api/calendar${query ? `?${query}` : ''}`);
    const box = el('div', { class: 'blue-box' });
    this.agenda = el('div', { class: 'agenda' });
    this.agenda.append(el('div', { class: 'legend' },
      ...data.calendars.map((c) => el('span', {}, el('span', { class: 'swatch', style: `background:${c.color}` }), c.name))));
    for (const day of data.days) {
      this.agenda.append(el('div', { class: day.events.length ? 'day-head' : 'day-head empty-day' }, this.ctx.fmt.calendarDay(day.date)));
      if (!day.events.length) continue;
      for (const event of day.events) {
        this.agenda.append(el('div', { class: 'event' },
          el('span', { class: 'bar', style: `background:${event.color}` }),
          el('span', { class: 'when' }, eventWhen(event, this.ctx.fmt)),
          el('span', { class: 'what' }, event.title, event.location ? el('span', { class: 'where' }, event.location) : null)));
      }
    }
    if (data.errors.length) this.agenda.append(el('div', { class: 'notice' }, `Could not load: ${data.errors.join(', ')}`));
    box.append(this.agenda);
    root.append(el('div', { class: 'body' }, box));
    this.box = box;
  }

  start(durationMs) {
    const overflow = this.agenda.scrollHeight - this.box.clientHeight;
    if (overflow <= 0) return;
    const travel = Math.max(1000, durationMs - TRANSITION_MS - 6000);
    this.agenda.style.transition = `transform ${travel}ms linear 3000ms`;
    requestAnimationFrame(() => { this.agenda.style.transform = `translateY(${-overflow}px)`; });
  }

  durationMs() { return this.cfg.seconds * 1000; }
}

function fmtNum(value, digits = 0) {
  return value == null ? '--' : Number(value).toFixed(digits);
}

class TempestSlide {
  constructor(cfg, ctx) { this.cfg = cfg; this.ctx = ctx; }

  titles() { return [this.data ? this.data.station : 'Tempest', 'Conditions']; }

  async prepare(root) {
    const data = this.data = await getJson('api/tempest');
    const c = data.current;
    const trend = { rising: 'Rising', falling: 'Falling', steady: 'Steady' }[c.pressure_trend] || '';
    const stat = (label, value) => el('div', { class: 'stat' }, el('span', { class: 'label' }, label), el('span', {}, value));
    const stats = [
      stat('Humidity:', `${fmtNum(c.humidity)}%`),
      stat('Dewpoint:', `${fmtNum(c.dew_point)}°`),
      stat('Feels Like:', `${fmtNum(c.feels_like)}°`),
      stat('Pressure:', `${fmtNum(c.pressure, 2)} ${trend}`),
      stat('Wind:', `${c.wind_cardinal || ''} ${fmtNum(c.wind_avg)} mph`),
      stat('Gusts:', `${fmtNum(c.wind_gust)} mph`),
      stat('UV Index:', fmtNum(c.uv, 1)),
      stat('Rain Today:', `${fmtNum(c.rain_today, 2)} in`),
    ];
    if (c.lightning_3hr) stats.push(stat('Lightning 3h:', c.lightning_3hr));
    const extended = data.daily.map((d) => el('div', { class: 'day' },
      el('div', { class: 'dow' }, this.ctx.fmt.weekday.format(new Date(d.day_start * 1000)).toUpperCase()),
      el('img', { src: d.icon, alt: '' }),
      el('div', {}, el('span', { class: 'hi' }, fmtNum(d.high)), ' ', el('span', { class: 'lo' }, fmtNum(d.low)))));
    root.append(el('div', { class: 'body' }, el('div', { class: 'blue-box' },
      el('div', { class: 'conditions' },
        el('div', { class: 'now' },
          el('div', { class: 'temp' }, `${fmtNum(c.temperature)}°`),
          el('img', { class: 'icon', src: c.icon, alt: '' }),
          el('div', { class: 'cond-text' }, c.conditions || '')),
        el('div', { class: 'stats' }, ...stats)),
      el('div', { class: 'extended' }, ...extended))));
  }

  start() {}

  durationMs() { return this.cfg.seconds * 1000; }
}

class GallerySlide {
  constructor(cfg, ctx) { this.cfg = cfg; this.ctx = ctx; this.timers = []; }

  fullscreen() { return true; }

  async prepare(root) {
    const items = await this.items();
    if (!items.length) throw new Error(`${this.cfg.type}: nothing to show`);
    const loaded = await Promise.all(items.map((item) => loadImage(item.url).then((img) => ({ img, item }), () => null)));
    this.shots = loaded.filter(Boolean);
    if (!this.shots.length) throw new Error(`${this.cfg.type}: no images loaded`);
    this.caption = el('div', { class: 'caption' });
    for (const { img } of this.shots) {
      img.className = 'photo';
      root.append(img);
    }
    root.append(this.caption);
  }

  show(i) {
    this.shots.forEach(({ img }, j) => img.classList.toggle('shown', i === j));
    this.caption.textContent = this.captionFor(this.shots[i].item);
  }

  start() {
    this.shots.forEach((_, i) => this.timers.push(setTimeout(() => this.show(i), i * this.cfg.seconds_each * 1000)));
  }

  durationMs() { return (this.shots ? this.shots.length : this.cfg.count) * this.cfg.seconds_each * 1000; }

  destroy() { this.timers.forEach(clearTimeout); }
}

class PhotosSlide extends GallerySlide {
  async items() { return (await getJson(`api/photos?count=${this.cfg.count}`)).photos; }

  captionFor(photo) {
    const parts = [photo.city, photo.taken_at ? this.ctx.fmt.monthYear.format(new Date(photo.taken_at)) : null];
    return parts.filter(Boolean).join(', ');
  }
}

class CamsSlide extends GallerySlide {
  async items() {
    const cams = (await getJson(`api/cams?count=${this.cfg.count}`)).cams;
    return cams;
  }

  captionFor(cam) { return `${cam.name}  LIVE`; }
}

class RadarSlide {
  constructor(cfg, ctx) { this.cfg = cfg; this.ctx = ctx; this.timer = null; }

  titles() { return [this.data ? this.data.name : 'Local', 'Radar']; }

  async prepare(root) {
    const data = this.data = await getJson(`api/radar/${encodeURIComponent(this.cfg.map)}`);
    const frames = await Promise.all(data.frames.map((f) => loadImage(f.url).then((img) => ({ img, time: f.time }), () => null)));
    this.frames = frames.filter(Boolean);
    if (!this.frames.length) throw new Error('no radar frames loaded');
    const body = el('div', { class: 'body' });
    for (const { img } of this.frames) {
      img.className = 'radar-frame';
      body.append(img);
    }
    this.label = el('div', { class: 'radar-time' });
    body.append(this.label, el('div', { class: 'attribution' }, 'Radar: NWS via Iowa Environmental Mesonet / Map: Esri'));
    root.append(body);
  }

  start() {
    let i = 0;
    const tick = () => {
      this.frames.forEach(({ img }, j) => img.classList.toggle('shown', i === j));
      this.label.textContent = this.ctx.fmt.time.format(new Date(this.frames[i].time));
      const last = i === this.frames.length - 1;
      i = last ? 0 : i + 1;
      this.timer = setTimeout(tick, last ? RADAR_HOLD_MS : RADAR_STEP_MS);
    };
    tick();
  }

  durationMs() { return this.cfg.seconds * 1000; }

  destroy() { clearTimeout(this.timer); }
}

class MountainSlide {
  constructor(cfg, ctx) { this.cfg = cfg; this.ctx = ctx; }

  titles() { return ['Mountain', 'Report']; }

  async prepare(root) {
    const data = await getJson('api/mountain');
    const cell = (cls, text) => el('span', { class: cls }, text);
    const rows = data.sites.map((s) => el('div', { class: 'mtn-row' },
      el('span', { class: 'mtn-name' }, s.name, el('span', { class: 'mtn-elev' }, s.elevation_ft ? `${Math.round(s.elevation_ft).toLocaleString('en-US')} ft` : '')),
      cell('mtn-num', `${fmtNum(s.temperature)}°`),
      cell('mtn-num mtn-range', `${fmtNum(s.temp_high)}/${fmtNum(s.temp_low)}`),
      cell('mtn-num', s.snow_depth == null ? '--' : `${fmtNum(s.snow_depth)}"`),
      cell('mtn-num mtn-new', s.snow_24h == null ? '--' : `${fmtNum(s.snow_24h)}"`)));
    const newest = data.sites.map((s) => s.observed_at).filter(Boolean).sort().pop();
    root.append(el('div', { class: 'body' }, el('div', { class: 'blue-box' },
      el('div', { class: 'mtn-head' },
        el('span', { class: 'mtn-name' }, 'SNOTEL Site'),
        cell('mtn-num', 'Temp'), cell('mtn-num mtn-range', 'Hi/Lo'), cell('mtn-num', 'Depth'), cell('mtn-num mtn-new', 'New 24h')),
      ...rows,
      el('div', { class: 'mtn-foot' }, newest ? `As of ${this.ctx.fmt.time.format(new Date(newest))}  /  NRCS SNOTEL` : 'NRCS SNOTEL'))));
  }

  start() {}

  durationMs() { return this.cfg.seconds * 1000; }
}

class Ws4kpSlide {
  constructor(cfg, ctx) { this.cfg = cfg; this.ctx = ctx; }

  fullscreen() { return true; }

  prepare(root) {
    return new Promise((resolve) => {
      const frame = el('iframe', { class: 'ws4kp', src: this.cfg.src, allow: 'autoplay; screen-wake-lock' });
      frame.addEventListener('load', () => resolve(), { once: true });
      root.append(frame, el('div', { class: 'ws4kp-place' }, `${this.cfg.name} Weather`));
      setTimeout(resolve, PREPARE_LEAD_MS);
    });
  }

  start() {}

  durationMs() { return this.cfg.seconds * 1000; }
}

const SLIDE_TYPES = {
  calendar: CalendarSlide,
  tempest: TempestSlide,
  photos: PhotosSlide,
  radar: RadarSlide,
  ws4kp: Ws4kpSlide,
  cams: CamsSlide,
  mountain: MountainSlide,
};

function minutesOfDay(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}

class QuietHours {
  constructor(spec, timeZone) {
    this.start = minutesOfDay(spec.start);
    this.end = minutesOfDay(spec.end);
    this.clock = new Intl.DateTimeFormat('en-US', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  }

  minuteOf(when) {
    const parts = Object.fromEntries(this.clock.formatToParts(when).map((p) => [p.type, p.value]));
    return Number(parts.hour) * 60 + Number(parts.minute);
  }

  active(now = new Date()) {
    const minute = this.minuteOf(now);
    return this.start <= this.end
      ? minute >= this.start && minute < this.end
      : minute >= this.start || minute < this.end;
  }

  /** Epoch ms of the next end; the second pass corrects for a DST shift overnight. */
  endsAt(now = new Date()) {
    const minutesLeft = (when) => (this.end - this.minuteOf(when) + 1440) % 1440;
    let at = now.getTime() - (now.getTime() % 60000) + minutesLeft(now) * 60000;
    const drift = minutesLeft(new Date(at));
    if (drift) at += (drift > 720 ? drift - 1440 : drift) * 60000;
    return at;
  }
}

function setDisplay(on) {
  $('#quiet').classList.toggle('shown', !on);
  if (window.FramestarKiosk) window.FramestarKiosk.setDisplayOn(on);
}

async function sleepThroughQuietHours(quiet) {
  if (!quiet || !quiet.active()) return;
  $('#quiet').classList.add('shown');
  if (window.FramestarKiosk && window.FramestarKiosk.sleepUntil) window.FramestarKiosk.sleepUntil(quiet.endsAt());
  else setDisplay(false);
  while (quiet.active()) await sleep(QUIET_POLL_MS);
  setDisplay(true);
  window.location.reload();
  await new Promise(() => {});
}

function setTitles(lines) {
  $('#title-1').textContent = lines[0] || '';
  $('#title-2').textContent = lines[1] || '';
}

function startClock({ fmt, quiet }) {
  const tick = () => {
    if (quiet && quiet.active()) return;
    const now = new Date();
    $('#clock-time').textContent = fmt.clockTime.format(now);
    $('#clock-date').textContent = fmt.clockDate.format(now).toUpperCase();
  };
  tick();
  setInterval(tick, 1000);
}

async function crawlMessages(config, fmt) {
  const messages = [];
  if (config.features.tempest) {
    try {
      const t = await getJson('api/tempest');
      const c = t.current;
      messages.push(`${t.station}: ${fmtNum(c.temperature)}°F ${c.conditions || ''}, wind ${c.wind_cardinal || ''} ${fmtNum(c.wind_avg)} mph`);
    } catch (e) { console.warn('crawl tempest', e); }
  }
  if (config.features.calendar) {
    try {
      const cal = await getJson('api/calendar');
      const now = Date.now();
      const upcoming = cal.days.slice(0, 2).flatMap((d) => d.events.map((e) => ({ ...e, day: d.date })))
        .filter((e) => e.all_day || new Date(e.start).getTime() > now)
        .slice(0, 5);
      for (const e of upcoming) {
        const day = e.day === cal.days[0].date ? 'Today' : 'Tomorrow';
        messages.push(`${day} ${eventWhen(e, fmt).toLowerCase()}: ${e.title}`);
      }
    } catch (e) { console.warn('crawl calendar', e); }
  }
  return messages.length ? messages : [config.title];
}

async function runCrawl(config, { fmt, quiet }) {
  const text = $('#crawl-text');
  for (;;) {
    if (quiet && quiet.active()) {
      text.textContent = '';
      await sleep(QUIET_POLL_MS);
      continue;
    }
    text.textContent = (await crawlMessages(config, fmt)).join('   --   ');
    const distance = STAGE_W + text.scrollWidth;
    const passMs = (distance / CRAWL_PX_PER_SEC) * 1000;
    const passes = Math.max(1, Math.ceil(CRAWL_REFRESH_MS / passMs));
    for (let i = 0; i < passes; i += 1) {
      text.style.transition = 'none';
      text.style.transform = `translateX(${STAGE_W}px)`;
      text.getBoundingClientRect();
      text.style.transition = `transform ${passMs}ms linear`;
      text.style.transform = `translateX(${-text.scrollWidth}px)`;
      await sleep(passMs);
    }
  }
}

async function prepareSlide(cfg, ctx) {
  const Type = SLIDE_TYPES[cfg.type];
  const slide = new Type(cfg, ctx);
  const root = el('div', { class: 'slide' });
  if (slide.fullscreen && slide.fullscreen()) root.classList.add('fullscreen');
  $('#slides').append(root);
  try {
    await slide.prepare(root);
    return { slide, root };
  } catch (e) {
    console.warn(`slide ${cfg.type} failed`, e);
    root.remove();
    if (slide.destroy) slide.destroy();
    return null;
  }
}

async function runShow(config, ctx) {
  const bootedAt = Date.now();
  const query = new URLSearchParams(window.location.search);
  const hold = query.has('hold');
  let index = Number(query.get('start') || 0) % config.slides.length;
  let current = null;
  let failures = 0;
  await sleepThroughQuietHours(ctx.quiet);
  let next = prepareSlide(config.slides[index], ctx);
  for (;;) {
    const prepared = await next;
    index = (index + 1) % config.slides.length;
    if (!prepared) {
      failures += 1;
      if (failures >= config.slides.length) await sleep(30000);
      next = prepareSlide(config.slides[index], ctx);
      continue;
    }
    failures = 0;
    if (prepared.slide.titles) setTitles(prepared.slide.titles());
    prepared.root.getBoundingClientRect();
    prepared.root.classList.add('active');
    if (current) {
      const old = current;
      old.root.classList.remove('active');
      old.root.classList.add('leaving');
      setTimeout(() => { if (old.slide.destroy) old.slide.destroy(); old.root.remove(); }, TRANSITION_MS + 100);
    }
    current = prepared;
    const duration = prepared.slide.durationMs();
    prepared.slide.start(duration);
    if (hold) return;
    await sleep(Math.max(0, duration - PREPARE_LEAD_MS));
    if (index === 0 && Date.now() - bootedAt > RELOAD_AFTER_MS) {
      await sleep(Math.min(duration, PREPARE_LEAD_MS));
      window.location.reload();
      return;
    }
    if (ctx.quiet && ctx.quiet.active()) {
      await sleep(Math.min(duration, PREPARE_LEAD_MS));
      if (current.slide.destroy) current.slide.destroy();
      current.root.remove();
      await sleepThroughQuietHours(ctx.quiet);
    }
    next = prepareSlide(config.slides[index], ctx);
    const [result] = await Promise.all([next, sleep(Math.min(duration, PREPARE_LEAD_MS))]);
    next = Promise.resolve(result);
  }
}

async function main() {
  fitStage();
  window.addEventListener('resize', fitStage);
  let config;
  for (;;) {
    try {
      config = await getJson('api/config');
      break;
    } catch (e) {
      console.warn('config', e);
      await sleep(10000);
    }
  }
  const ctx = {
    fmt: new Formatters(config.timezone),
    quiet: config.quiet_hours ? new QuietHours(config.quiet_hours, config.timezone) : null,
  };
  setDisplay(true);
  setTitles([config.title, '']);
  startClock(ctx);
  runCrawl(config, ctx);
  runShow(config, ctx);
}

main();
