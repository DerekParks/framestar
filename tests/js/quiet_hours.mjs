import { readFileSync } from 'node:fs';
const src = readFileSync(new URL("../../framestar/static/app.js", import.meta.url), "utf8");
const body = src.slice(src.indexOf('function minutesOfDay'), src.indexOf('function setDisplay'));
const QuietHours = new Function(body + '; return QuietHours;')();
const q = new QuietHours({ start: '22:00', end: '07:00' }, 'America/Denver');
const local = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Denver', dateStyle: 'short', timeStyle: 'long' });
let bad = 0;
for (const [label, iso] of [
  ['normal night 22:00', '2026-10-16T04:00:00Z'],
  ['normal 03:17:42', '2026-10-16T09:17:42Z'],
  ['fall back night 22:00', '2026-11-01T04:00:00Z'],
  ['fall back after shift 02:30 MST', '2026-11-01T09:30:00Z'],
  ['spring fwd night 22:00', '2027-03-14T05:00:00Z'],
  ['spring fwd 23:59:59', '2027-03-14T06:59:59Z'],
  ['spring fwd 03:30 MDT', '2027-03-14T09:30:00Z'],
  ['06:59:30', '2026-10-16T12:59:30Z'],
]) {
  const now = new Date(iso), at = new Date(q.endsAt(now));
  const ok = q.minuteOf(at) === 420 && at.getUTCSeconds() === 0 && at > now && at - now <= 10 * 3600e3 && !q.active(at) && q.active(new Date(at - 60000));
  bad += !ok;
  console.log(ok ? 'ok ' : 'BAD', label.padEnd(32), local.format(now), '->', local.format(at));
}
const day = new QuietHours({ start: '01:00', end: '05:30' }, 'America/Denver');
const at = new Date(day.endsAt(new Date('2026-10-16T08:00:00Z')));
console.log(day.minuteOf(at) === 330 ? 'ok ' : 'BAD', 'non-wrapping window ->', local.format(at)); bad += day.minuteOf(at) !== 330;
process.exit(bad);
