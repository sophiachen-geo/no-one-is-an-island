// Render QA for kansai/index.html — drives the real page in Chromium and checks what a reader sees.
//
//   node kansai/qa/check_render.mjs <page.html> <report.json> [--shots <dir>]
//
// Writes a JSON report {errors, warnings, inventory, usedPoints, stats}; kansai/qa/run.py turns it
// into pass/fail. Playwright comes from `npm i playwright` (CI) or $PLAYWRIGHT_MODULE (local).
// QA_FONT_CACHE=<dir> serves Google Fonts through a local cache (for sandboxes without direct access).
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

let pw;
try { pw = await import('playwright'); } catch { pw = await import(process.env.PLAYWRIGHT_MODULE || '/opt/node22/lib/node_modules/playwright/index.mjs'); }
const { chromium } = pw.default || pw;

const [,, pagePath, reportPath, ...rest] = process.argv;
const shotsDir = rest[0] === '--shots' ? rest[1] : null;
const chartsOnly = rest.includes('--charts-only');   // self-test: box and overflow rules on a small synthetic page
if (shotsDir) mkdirSync(shotsDir, { recursive: true });
const url = pathToFileURL(resolve(pagePath)).href;
const errors = [], warnings = [];
const err = (check, msg, where = '') => errors.push({ check, msg, where });
const OVERFLOW_SEL = '.picto-row figcaption, .stats > div, .chain .i, .board p, figcaption, .legend span, .plans a.pl, .chips a, .gstats div, td, th, button, .viewname, .mini figcaption span';
const warn = (check, msg, where = '') => warnings.push({ check, msg, where });

const browser = await chromium.launch();

async function open(viewport, opts = {}) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const cache = process.env.QA_FONT_CACHE;
  await ctx.route(/cyberjapandata\.gsi\.go\.jp/, (route) => route.abort());   // imagery is checked geometrically, not fetched
  if (opts.noFonts) {
    await ctx.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());   // what a reader sees when the web fonts fail
  } else if (cache) {
    mkdirSync(cache, { recursive: true });
    await ctx.route(/fonts\.(googleapis|gstatic)\.com/, async (route) => {
      const u = route.request().url(), f = resolve(cache, createHash('md5').update(u).digest('hex'));
      try { if (!existsSync(f)) execFileSync('curl', ['-s', '--max-time', '30', '-A', 'Mozilla/5.0 Chrome/140', '-o', f, u]); } catch {}
      if (!existsSync(f)) return route.abort();
      await route.fulfill({ status: 200, body: readFileSync(f), headers: { 'content-type': u.includes('googleapis') ? 'text/css' : 'font/woff2', 'access-control-allow-origin': '*' } });
    });
  }
  const page = await ctx.newPage();
  page.on('pageerror', (e) => err('js-error', e.message, viewport.width + 'px'));
  page.on('console', (m) => { if (m.type() === 'error' && !/ERR_FAILED|net::|Failed to load resource/.test(m.text())) err('console-error', m.text(), viewport.width + 'px'); });
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  // the Kamikura micro-study loads when a reader scrolls near it; every pass checks it built
  await page.evaluate(() => (window.__QA && window.__QA.kmkLoad ? window.__QA.kmkLoad() : null));
  // the field notes load the same way
  await page.evaluate(() => (window.__QA && window.__QA.fnLoad ? window.__QA.fnLoad() : null));
  await page.waitForTimeout(300);
  return { ctx, page };
}

// ---------------------------------------------------------------- desktop pass
if (chartsOnly) {
  for (const noFonts of [false, true]) {
    const o = await open({ width: 1440, height: 900 }, { noFonts });
    await chartChecks(o.page, noFonts ? 'fallback-font' : '1440px');
    await htmlOverflow(o.page, noFonts ? 'fallback-font' : '1440px');
    await o.ctx.close();
  }
  await browser.close();
  writeFileSync(reportPath, JSON.stringify({ errors, warnings, inventory: [], usedPoints: [], tiles: [], links: [] }, null, 1));
  console.log(`charts-only QA: ${errors.length} error(s)`);
  process.exit(0);
}
const { ctx, page } = await open({ width: 1440, height: 900 });
const hasQA = await page.evaluate(() => !!window.__QA);
if (!hasQA) { err('qa-hook', 'window.__QA missing — page script failed or hook removed'); }
// in-page links (the contents pane): every #anchor leads to an element
const deadAnchors = await page.evaluate(() => [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute('href'))
  .filter((h) => h.length > 1 && !document.getElementById(decodeURIComponent(h.slice(1)))));
deadAnchors.forEach((h) => err('anchors', `in-page link ${h} leads nowhere`));

// 1. references: every attribute/key the page uses must resolve to data
if (hasQA) {
  const refs = await page.evaluate(() => {
    const Q = window.__QA, out = [], G = Q.G, words = (s) => (s || '').split(/\s+/).filter(Boolean);
    const groups = new Set(Q.groups), layers = new Set(Q.layers);
    document.querySelectorAll('.step').forEach((s, i) => {
      const v = s.getAttribute('data-view'); if (!G.views[v]) out.push(['view', `step ${i}: data-view "${v}" not in GEO.views`]);
      words(s.getAttribute('data-on')).forEach((n) => { if (!layers.has(n) && !(Q.ALIASES && Q.ALIASES[n]) && !(Q.pseudo || []).includes(n)) out.push(['layer', `step ${i}: data-on "${n}" has no layer`]); });
      words(s.getAttribute('data-edge')).forEach((n) => { if (!Q.ptOf(n)) out.push(['point', `step ${i}: data-edge "${n}" is not a point`]); });
      words(s.getAttribute('data-overlay')).forEach((n) => { if (!groups.has(n)) out.push(['overlay', `step ${i}: data-overlay "${n}" has no labels/markers`]); });
      words(s.getAttribute('data-legend')).forEach((n) => { if (!Q.LEG[n] && !(Q.GROUPLEG && Q.GROUPLEG[n])) out.push(['legend', `step ${i}: data-legend "${n}" not in LEG`]); });
      if (!s.getAttribute('data-name')) out.push(['view', `step ${i}: missing data-name`]);
    });
    Q.LABELS.forEach((l) => { if (!Q.ptOf(l[0])) out.push(['point', `label "${l[1]}" → unknown point "${l[0]}"`]); });
    Q.MARKERS.forEach((m) => { if (!Q.ptOf(m[0])) out.push(['point', `marker ${m[1]} → unknown point "${m[0]}"`]); });
    Q.LINKS.forEach((l) => { if (!Q.ptOf(l[0]) || !Q.ptOf(l[1])) out.push(['point', `link ${l[0]}→${l[1]} unresolved`]); });
    document.querySelectorAll('[data-hl]').forEach((e) => {
      const k = e.getAttribute('data-hl'), h = Q.HL[k];
      if (!h) { out.push(['highlight', `data-hl "${k}" has no entry in HL`]); return; }
      (h.pts || []).forEach((p) => { if (!Q.ptOf(p)) out.push(['highlight', `HL "${k}": point "${p}" missing`]); });
      (h.layers || []).forEach((l) => { if (!layers.has(l)) out.push(['highlight', `HL "${k}": layer "${l}" missing`]); });
      if (h.fit && h.fit.startsWith('view:') && !G.views[h.fit.slice(5)]) out.push(['highlight', `HL "${k}": view "${h.fit}" missing`]);
    });
    Q.MEDIA.forEach((m) => { if (!Q.ptOf(m.pt)) out.push(['media', `picture "${m.id}" → unknown point "${m.pt}"`]); words(m.groups).forEach((gname) => { if (!groups.has(gname)) out.push(['media', `picture "${m.id}" → unknown overlay group "${gname}"`]); }); });
    Q.KPLACES.forEach((p) => { if (!Q.ptOf(p[0])) out.push(['point', `system map place "${p[0]}" missing`]); });
    Q.FACETS.forEach((f, i) => {
      (f.layers || []).forEach((l) => { if (!Q.LD(l[0])) out.push(['layer', `facet ${i} "${f.q}": layer "${l[0]}" missing`]); });
      (f.pts || []).forEach((p) => { if (!Q.ptOf(p[0])) out.push(['point', `facet ${i} "${f.q}": point "${p[0]}" missing`]); });
    });
    return out;
  });
  refs.forEach(([k, m]) => err('refs-' + k, m));
}

// 2. land fill actually renders (a CSS specificity slip once painted the whole map in sea colour)
const fills = await page.evaluate(() => {
  const land = document.querySelector('#world .land path'), sea = document.querySelector('#world .sea');
  return { land: land && getComputedStyle(land).fill, sea: sea && getComputedStyle(sea).fill };
});
if (!fills.land || fills.land === 'none' || fills.land === fills.sea) err('land-fill', `land fill is "${fills.land}" (sea "${fills.sea}")`);

// 3. per-step checks, desktop + mobile
async function stepChecks(pg, tag) {
  const n = await pg.evaluate(() => { if (window.__QA) window.__QA.hold(true); return window.__QA ? window.__QA.steps : 0; });
  for (let i = 0; i < n; i++) {
    await pg.evaluate((i) => document.querySelectorAll('.step')[i].scrollIntoView({ block: 'center', behavior: 'instant' }), i);   // the page scrolls smoothly; a check must not wait on it
    await pg.waitForTimeout(60);
    const r = await pg.evaluate((i) => {
      const Q = window.__QA; Q.activate(i);
      const c = Q.cam(), F = Q.frame, hw = c.W / 2 / c.k, hh = c.H / 2 / c.k, eps = 0.05;
      const vis = [c.cx - hw, c.cy - hh, c.cx + hw, c.cy + hh];
      const s = document.querySelectorAll('.step')[i], v = Q.G.views[s.getAttribute('data-view')];
      const ix = Math.max(0, Math.min(vis[2], v[2]) - Math.max(vis[0], v[0])), iy = Math.max(0, Math.min(vis[3], v[3]) - Math.max(vis[1], v[1]));
      const seen = ix * iy / ((v[2] - v[0]) * (v[3] - v[1]));
      const svg = document.getElementById('map');
      const sr = svg.getBoundingClientRect();
      const labs = [...document.querySelectorAll('#overlay .og text')].filter((t) => {
        const g = t.closest('.og'); return g && g.getAttribute('opacity') !== '0' && g.style.display !== 'none' && !t.classList.contains('hidden');
      }).map((t) => { const b = t.getBoundingClientRect(); return { t: t.textContent, x: b.left - sr.left, y: b.top - sr.top, w: b.width, h: b.height }; });
      const hiddenEls = [...document.querySelectorAll('#overlay .og text.hidden')].filter((t) => { const g = t.closest('.og'); return g && g.getAttribute('opacity') !== '0'; });
      const hidden = hiddenEls.filter((t) => !t.classList.contains('key')).map((t) => t.textContent);
      const edgeList = (s.getAttribute('data-edge') || '').split(/\s+/).filter(Boolean);
      const offKey = (t) => { const L = Q.LABELS.find((l) => l[1] === t.textContent || (l[1].split(' · ')[0] + ' · ' + (l[1].split(' · ')[1] || '')) === t.textContent); if (!L) return false;
        const w = Q.ptOf(L[0]), sx = (w[0] - c.cx) * c.k + c.W / 2, sy = (w[1] - c.cy) * c.k + c.H / 2; return (sx < 0 || sy < 0 || sx > c.W || sy > c.H) && edgeList.includes(L[0]); };
      const hiddenKey = hiddenEls.filter((t) => t.classList.contains('key') && !offKey(t)).map((t) => t.textContent);
      const overlaps = [];
      for (let a = 0; a < labs.length; a++) for (let b = a + 1; b < labs.length; b++) {
        const A = labs[a], B = labs[b];
        const ox = Math.min(A.x + A.w, B.x + B.w) - Math.max(A.x, B.x), oy = Math.min(A.y + A.h, B.y + B.h) - Math.max(A.y, B.y);
        if (ox > 2 && oy > 0.3 * Math.min(A.h, B.h)) overlaps.push(A.t + ' ⟷ ' + B.t);
      }
      const outside = labs.filter((L) => L.x < -1 || L.y < -1 || L.x + L.w > sr.width + 1 || L.y + L.h > sr.height + 1).map((L) => L.t);
      const on = (s.getAttribute('data-on') || '').split(/\s+/).filter(Boolean);
      const off = on.filter((k) => { const g = document.querySelector('#world .L.' + CSS.escape(k)); return g && !g.classList.contains('on'); });
      const legendItems = document.querySelectorAll('#legend span').length;
      // every switched-on layer that means something is explained in the legend
      const legText = document.getElementById('legend').textContent;
      const onLayers = [...document.querySelectorAll('#world .L.on')].map((g) => [...g.classList].find((c) => c !== 'L' && c !== 'on'));
      const missingLeg = onLayers.filter((n) => Q.LAYER_LEG[n] && !Q.BASE.includes(n)).filter((n) => {
        const k = Q.LAYER_LEG[n]; const items = Q.GROUPLEG[k] || [Q.LEG[k]];
        return items.some((it) => it && !legText.includes(it[3]));
      });
      // places a step names but cannot show get an arrow at the frame edge
      const edgeWant = (s.getAttribute('data-edge') || '').split(/\s+/).filter(Boolean).filter((k) => {
        const w = Q.ptOf(k), sx = (w[0] - c.cx) * c.k + c.W / 2, sy = (w[1] - c.cy) * c.k + c.H / 2; return sx < 6 || sy < 6 || sx > c.W - 6 || sy > c.H - 6;
      });
      const edgeGot = document.querySelectorAll('#overlay .edgeg .edge').length;
      const clab = [...document.querySelectorAll('#overlay .clab text')].map((t) => t.textContent);
      return { name: s.getAttribute('data-name'), inFrame: vis[0] >= F[0] - eps && vis[1] >= F[1] - eps && vis[2] <= F[2] + eps && vis[3] <= F[3] + eps,
        vis, seen, overlaps, outside, hidden, hiddenKey, off, legend: legendItems, wantLegend: !!(s.getAttribute('data-legend') || '').trim(), nlabels: labs.length,
        missingLeg, edgeWant, edgeGot, clab, micro: onLayers.some((n) => /^micro_/.test(n)) };
    }, i);
    const where = `${tag} step ${i} “${r.name}”`;
    if (!r.inFrame) err('camera-frame', `view shows area outside the data frame ${JSON.stringify(r.vis.map((v) => +v.toFixed(1)))}`, where);
    if (r.seen < 0.6) warn('camera-crop', `only ${(r.seen * 100).toFixed(0)}% of the step’s view is on screen`, where);
    r.overlaps.forEach((o) => err('label-overlap', o, where));
    r.outside.forEach((o) => err('label-outside', o, where));
    r.off.forEach((o) => err('layer-off', `data-on layer "${o}" not switched on`, where));
    if (r.wantLegend && !r.legend) err('legend-empty', 'legend requested but empty', where);
    r.missingLeg.forEach((n) => err('legend-missing', `layer "${n}" is on but the legend does not explain it`, where));
    if (r.edgeWant.length && r.edgeGot < r.edgeWant.length) err('edge-pointer', `off-screen place(s) ${r.edgeWant.join(', ')} have no edge arrow`, where);
    if (tag === 'desktop' && r.micro && r.clab.length < 2) err('contour-labels', `ground contours are drawn but only ${r.clab.length} carry their height`, where);
    if (r.hidden.length) warn('label-hidden', `${r.hidden.length} label(s) hidden by declutter: ${r.hidden.join(' | ')}`, where);
    // labels the text refers to (class "key") must be readable at the step's own view on desktop; phones can zoom
    if (r.hiddenKey.length) (tag === 'desktop' ? err : warn)('key-label-hidden', `label(s) the text relies on are hidden: ${r.hiddenKey.join(' | ')}`, where);
    if (shotsDir) { await pg.waitForTimeout(900); await pg.screenshot({ path: `${shotsDir}/${tag}_${String(i).padStart(2, '0')}.png` }); }  // let the 0.7 s layer fade finish
  }
}
if (hasQA) await stepChecks(page, 'desktop');

// 4. zoom controls: in / out / reset, clamps, wheel + drag
if (hasQA) {
  await page.evaluate(() => { window.__QA.hold(false); document.querySelectorAll('.step')[0].scrollIntoView({ block: 'center', behavior: 'instant' }); });
  await page.waitForTimeout(1600);
  const z = await page.evaluate(async () => {
    const Q = window.__QA; Q.activate(0);
    const k0 = Q.cam().k, btn = (z) => document.querySelector(`.zoomctl button[data-z="${z}"]`);
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    btn('in').click(); const kIn = Q.cam().k;
    btn('out').click(); btn('out').click(); btn('out').click(); btn('out').click(); btn('out').click(); btn('out').click();
    const cOut = Q.cam(), F = Q.frame, hw = cOut.W / 2 / cOut.k, hh = cOut.H / 2 / cOut.k;
    const outInFrame = cOut.cx - hw >= F[0] - 0.05 && cOut.cx + hw <= F[2] + 0.05 && cOut.cy - hh >= F[1] - 0.05 && cOut.cy + hh <= F[3] + 0.05;
    for (let j = 0; j < 30; j++) btn('in').click();
    const kMaxHit = Q.cam().k, sbr = document.querySelector('#scalebar rect'), bar = sbr ? +sbr.getAttribute('width') : null;
    btn('reset').click(); await wait(1500);
    const s = Q.stepCam(), c = Q.cam();
    return { k0, kIn, kOut: cOut.k, kMin: Q.kMin(), outInFrame, kMaxHit, K_MAX: Q.K_MAX, cam: c, step: s, bar, barW: +document.getElementById('scalebar').getAttribute('width'),
      reset: Math.abs(c.k - s.k) < 1e-6 * s.k && Math.abs(c.cx - s.cx) < 1e-3 && Math.abs(c.cy - s.cy) < 1e-3 };
  });
  if (!(z.kIn > z.k0 * 1.5 || z.k0 * 1.6 > z.K_MAX)) err('zoom', `zoom-in did not zoom (k ${z.k0} → ${z.kIn})`);
  if (Math.abs(z.kOut - z.kMin) > 1e-9) err('zoom', `zoom-out does not stop at the frame (k ${z.kOut}, kMin ${z.kMin})`);
  if (!z.outInFrame) err('zoom', 'zoomed-out view leaves the data frame');
  if (Math.abs(z.kMaxHit - z.K_MAX) > 1e-9) err('zoom', `zoom-in does not clamp at K_MAX (${z.kMaxHit})`);
  if (z.bar == null || z.bar > z.barW || z.bar < 20) err('zoom', `the scale bar at full zoom is ${z.bar} px in a ${z.barW} px box`);
  if (!z.reset) err('zoom', `reset button does not return to the step view (cam ${JSON.stringify(z.cam)} vs step ${JSON.stringify(z.step)})`);
  // wheel (ctrl) and drag go through the real input path
  const box = await page.locator('#map').boundingBox();
  if (box) {
    const k1 = await page.evaluate(() => window.__QA.cam().k);
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.keyboard.down('Control'); await page.mouse.wheel(0, -400); await page.keyboard.up('Control');
    await page.waitForTimeout(250);
    const k2 = await page.evaluate(() => window.__QA.cam().k);
    if (!(k2 > k1)) err('zoom', `ctrl+wheel did not zoom in (k ${k1} → ${k2})`);
    const c1 = await page.evaluate(() => window.__QA.cam());
    await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 - 120, box.y + box.height / 2 - 60, { steps: 6 }); await page.mouse.up();
    const c2 = await page.evaluate(() => window.__QA.cam());
    if (Math.hypot(c2.cx - c1.cx, c2.cy - c1.cy) < 1e-3) err('zoom', 'mouse drag did not pan the map');
  }
}

// 4b. interactions the text promises: hover-to-locate, pictures, the linked system map, imagery
let tiles = [], links = [], fnReport = { errors: [], tables: {}, prof: {}, strip: null };
if (hasQA) {
  const ia = await page.evaluate(async () => {
    const Q = window.__QA, out = [], steps = [...document.querySelectorAll('.step')], wait = (ms) => new Promise((r) => setTimeout(r, ms));
    Q.hold(true);
    // hover-to-locate: every tagged phrase lights its places (ring or edge arrow) and its layers
    for (const e of document.querySelectorAll('[data-hl]')) {
      const k = e.getAttribute('data-hl'), h = Q.HL[k]; if (!h) continue;
      const st = e.closest('.step'); if (st) Q.activate(steps.indexOf(st));
      Q.showHL(k);
      const rings = document.querySelectorAll('#overlay .hlg .hlring, #overlay .hlg .edge').length;
      if ((h.pts || []).length && rings < (h.pts || []).length) out.push(['highlight', `“${e.textContent.trim().slice(0, 40)}” (${k}) lights ${rings} of ${(h.pts || []).length} places`]);
      (h.layers || []).forEach((l) => { const g = document.querySelector('#world .L.' + CSS.escape(l)); if (!g || !g.classList.contains('on') || !g.classList.contains('hl')) out.push(['highlight', `“${k}”: layer ${l} does not light up`]); });
      if (!e.classList.contains('on')) out.push(['highlight', `“${k}”: the phrase itself is not marked while its places are lit`]);
      Q.clearHL();
    }
    // pictures: pulse ⇔ clickable ⇔ registered picture; each opens with its images
    const pulses = [...document.querySelectorAll('#overlay .pulse')];
    pulses.forEach((p) => { if (!Q.MEDIA.some((m) => m.id === p.getAttribute('data-media'))) out.push(['media', `a pulsing marker (${p.getAttribute('data-media')}) opens nothing`]); });
    const anims = [...document.querySelectorAll('#overlay *')].filter((n) => getComputedStyle(n).animationName === 'pulse' && !n.closest('.pulse'));
    if (anims.length) out.push(['media', `${anims.length} map element(s) pulse without being clickable`]);
    for (const m of Q.MEDIA) {
      const host = pulses.find((p) => p.getAttribute('data-media') === m.id);
      if (!host) { out.push(['media', `picture “${m.id}” has no pulsing marker on the map`]); continue; }
      const g = host.closest('.og'), gname = [...g.classList].includes('og') ? Object.keys(Q.groups).length : 0;
      const st = steps.findIndex((s) => (s.getAttribute('data-overlay') || '').split(/\s+/).some((n) => (m.groups || '').split(/\s+/).includes(n)));
      if (st < 0) { out.push(['media', `picture “${m.id}” belongs to no step`]); continue; }
      Q.activate(st); Q.openMedia(m.id); await wait(30);
      const card = document.getElementById('mcard'), slot = m.slot ? steps[st].querySelector(`.mslot[data-slot="${m.slot}"]`) : null;
      const box = slot && slot.classList.contains('open') ? slot : (!card.hidden ? card : null);
      if (!box) { out.push(['media', `picture “${m.id}” did not open`]); continue; }
      const imgs = [...box.querySelectorAll('img')];
      if (imgs.length !== m.images.length) out.push(['media', `picture “${m.id}” shows ${imgs.length} of ${m.images.length} images`]);
      for (const im of imgs) { if (!im.complete) await new Promise((r) => { im.onload = im.onerror = r; setTimeout(r, 3000); }); if (!im.naturalWidth) out.push(['media', `image ${im.getAttribute('src')} does not load`]); }
      if (!box.querySelector('.cr')) out.push(['media', `picture “${m.id}” has no credit line`]);
      const close = box.querySelector('.mclose'); if (!close) out.push(['media', `picture “${m.id}” cannot be closed`]); else close.click();
      await wait(20);
      if (!card.hidden || (slot && slot.classList.contains('open'))) out.push(['media', `picture “${m.id}” does not close`]);
    }
    // the system map and the long profile light the same place together
    for (const p of Q.KPLACES) {
      const a = document.querySelectorAll(`#ksmap .kp[data-place="${p[0]}"]`).length, b = document.querySelectorAll(`#valley .kp[data-place="${p[0]}"]`).length;
      if (!a || !b) { out.push(['linked-maps', `${p[1]} is on ${a ? 'the flat map' : 'the profile'} only`]); continue; }
      Q.lightPlace(p[0]);
      const lit = document.querySelectorAll(`.kp.lit[data-place="${p[0]}"]`).length;
      if (lit < 2) out.push(['linked-maps', `${p[1]}: lighting it lights ${lit} of 2 views`]);
    }
    Q.lightPlace(null);
    document.querySelectorAll('#valley .kp').forEach((g) => { if (!Q.KPLACES.some((p) => p[0] === g.getAttribute('data-place'))) out.push(['linked-maps', `profile place ${g.getAttribute('data-place')} is not on the flat map`]); });
    // the Kamikura micro-study: built, every system switch restyles the map and its legend without colliding labels,
    // the profile and the map light the same point, the camera stays inside the data frame
    const K = Q.kmk;
    if (!K || !K.ready) out.push(['kamikura', 'the micro-study did not build (data/kamikura.js)']);
    else {
      document.querySelectorAll('.kchip, .kcard, .kh').forEach((b) => { if (!Q.KSYS[b.getAttribute('data-ks')]) out.push(['kamikura', `“${b.textContent.trim().slice(0, 30)}” switches to an unknown system ${b.getAttribute('data-ks')}`]); });
      if (document.querySelectorAll('.kchip').length !== Object.keys(Q.KSYS).length) out.push(['kamikura', 'not every system has a switch']);
      const svgK = document.querySelector('#kmkmap svg.kmk-svg');
      for (const key of Object.keys(Q.KSYS)) {
        K.setSys(key, true); await document.fonts.ready; await wait(60);
        if (svgK.getAttribute('data-sys') !== key) out.push(['kamikura', `switch ${key} does not reach the map`]);
        const want = Q.KSYS[key].leg.split(' ').length, got = document.querySelectorAll('#kmkleg li').length;
        if (got !== want) out.push(['kamikura', `legend for ${key} shows ${got} of ${want} entries`]);
        const boxes = [...svgK.querySelectorAll('.kmk-ov text')].filter((t) => t.getClientRects().length && getComputedStyle(t).display !== 'none' && t.closest('g').style.display !== 'none')
          .map((t) => ({ t: t.textContent, r: t.getBoundingClientRect() }));
        for (let a = 0; a < boxes.length; a++) for (let b = a + 1; b < boxes.length; b++) {
          const A = boxes[a].r, B = boxes[b].r, ox = Math.min(A.right, B.right) - Math.max(A.left, B.left), oy = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
          if (ox > 2 && oy > 2) out.push(['kamikura', `${key}: map labels “${boxes[a].t}” and “${boxes[b].t}” overlap`]);
        }
        const mr = svgK.getBoundingClientRect();
        boxes.forEach((b) => { if (b.r.left < mr.left - 1 || b.r.right > mr.right + 1 || b.r.top < mr.top - 1 || b.r.bottom > mr.bottom + 1) out.push(['kamikura', `${key}: map label “${b.t}” leaves the map`]); });
      }
      // the ground under the map: every button swaps the image to its own layer and shows its colour scale (relief: none)
      const gimg = svgK.querySelector('image.k-relief'), D = window.__KMK;
      for (const b of document.querySelectorAll('.kbase-b')) {
        const key = b.getAttribute('data-kb'); K.setBase(key); await wait(30);
        const want = key === 'relief' ? D.img.href : (D.bases[key] || {}).href;
        if (!want || gimg.getAttribute('href') !== want) out.push(['kamikura', `ground “${key}” does not reach the map`]);
        const rp = document.getElementById('kmkramp');
        if ((key === 'relief') !== rp.hidden) out.push(['kamikura', `ground “${key}”: colour scale ${rp.hidden ? 'missing' : 'left over'}`]);
        if (b.getAttribute('aria-pressed') !== 'true') out.push(['kamikura', `ground “${key}” button is not marked pressed`]);
        if (key !== 'relief') {
          const ok = await new Promise((res) => { const im = new Image(); im.onload = () => res(im.naturalWidth > 1000); im.onerror = () => res(false); im.src = want; });
          if (!ok) out.push(['kamikura', `ground layer ${want} does not load`]);
          const svgR = rp.querySelector('svg'), vb = svgR && svgR.viewBox.baseVal;
          [...(svgR ? svgR.querySelectorAll('text') : [])].forEach((t) => { const bb = t.getBBox(); if (bb.x < -1 || bb.x + bb.width > vb.width + 1) out.push(['kamikura', `colour scale “${t.textContent}” leaves its box`]); });
        }
      }
      K.setBase('relief');
      // the three figures of the ground section are drawn from the data
      [['kmkfoot', 'path'], ['kmkscore', 'circle'], ['kmkoff', 'circle'], ['kmkclimb', 'circle'], ['kmksec', 'path'], ['kmktown', 'path'], ['kmkgaze', 'circle']].forEach(([id, tag]) => { if (!document.querySelectorAll(`#${id} ${tag}`).length) out.push(['kamikura', `figure #${id} is empty`]); });
      // the religious-flow figures: no label leaves its figure
      for (const id of ['kmkclimb', 'kmksec', 'kmktown', 'kmkgaze']) {
        const sv = document.getElementById(id), vb = sv && sv.viewBox.baseVal;
        [...(sv ? sv.querySelectorAll('text') : [])].forEach((t) => {
          const bb = t.getBBox(), m = t.getCTM(), s0 = sv.getCTM();
          const p0 = new DOMPoint(bb.x, bb.y).matrixTransform(m).matrixTransform(s0.inverse()), p1 = new DOMPoint(bb.x + bb.width, bb.y + bb.height).matrixTransform(m).matrixTransform(s0.inverse());
          const x0 = Math.min(p0.x, p1.x), x1 = Math.max(p0.x, p1.x), y0 = Math.min(p0.y, p1.y), y1 = Math.max(p0.y, p1.y);
          if (x0 < -1 || x1 > vb.width + 1 || y0 < -1 || y1 > vb.height + 1) out.push(['kamikura', `figure #${id}: “${t.textContent}” leaves the figure`]);
        });
      }
      // the two ground profiles are drawn at the vertical exaggeration their captions state
      for (const id of ['kmkfoot', 'kmkprof', 'kmkclimb', 'kmksec']) {
        const sv = document.getElementById(id), cap = sv && sv.closest('figure') && sv.closest('figure').querySelector('figcaption');
        const m = cap && (cap.textContent.match(/heights ×(\d+(?:\.\d+)?)/) || (/heights true to scale/.test(cap.textContent) ? [0, '1'] : null)), ve = sv ? parseFloat(sv.getAttribute('data-ve')) : NaN;
        if (!m || !(Math.abs(ve - parseFloat(m[1])) < 0.05)) out.push(['kamikura', `figure #${id} is drawn with heights ×${ve} but its caption says ${m ? '×' + m[1] : 'nothing'}`]);
      }
      K.setSys('all', true);
      K.setTr(400, false); await wait(20);
      const mk = document.querySelector('#kmkmap .ktrm'), cu = document.querySelector('#kmkprof .kpcur');
      if (!mk || mk.style.display === 'none' || !cu || cu.style.display === 'none') out.push(['kamikura', 'a point on the profile does not light on the map']);
      K.setTr(null);
      if ((mk && mk.style.display !== 'none') || (cu && cu.style.display !== 'none')) out.push(['kamikura', 'the transect marker does not clear']);
      const c0 = K.cam(); K.zoom(4, c0.W / 2, c0.H / 2); const c1 = K.cam();
      K.zoom(1e4, c0.W / 2, c0.H / 2); const kb = document.querySelector('#kmkmap .msb'), kr = kb && kb.querySelector('rect');
      if (!kr || +kr.getAttribute('width') > +kb.getAttribute('width') || +kr.getAttribute('width') < 20) out.push(['kamikura', `the scale bar at full zoom is ${kr && kr.getAttribute('width')} px in a ${kb && kb.getAttribute('width')} px box`]);
      K.zoom(1 / 64, c0.W / 2, c0.H / 2); K.zoom(1 / 64, c0.W / 2, c0.H / 2); K.zoom(1 / 64, c0.W / 2, c0.H / 2); const c2 = K.cam(); K.home(); const c3 = K.cam();
      if (!(c1.k > c0.k)) out.push(['kamikura', 'zoom in does nothing']);
      if (c2.k < c2.kmin - 1e-6 || c2.cx - c2.W / 2 / c2.k < c2.F[0] - 1e-6 || c2.cx + c2.W / 2 / c2.k > c2.F[2] + 1e-6 || c2.cy - c2.H / 2 / c2.k < c2.F[1] - 1e-6 || c2.cy + c2.H / 2 / c2.k > c2.F[3] + 1e-6)
        out.push(['kamikura', 'zooming out shows ground outside the data frame']);
      if (Math.abs(c3.k - c0.k) > 1e-6) out.push(['kamikura', 'reset does not return to the study area']);
    }
    // imagery: one switch drives every map; each map has one
    const btns = document.querySelectorAll('.satbtn').length, maps = document.querySelectorAll('#map, .mini svg.m, #ksmap svg.km, #kmkmap svg.kmk-svg, #fnmap svg.fn-svg').length;
    if (btns < maps) out.push(['satellite', `${maps} maps but ${btns} satellite switches`]);
    // the main map is shared by the stages and requests imagery only where it is on screen: bring it into view first
    document.getElementById('map').scrollIntoView({ block: 'center', behavior: 'instant' }); await wait(300);
    Q.satSet(true); await wait(50);
    if (!document.body.classList.contains('sat-on') || [...document.querySelectorAll('.satbtn')].some((b) => b.getAttribute('aria-pressed') !== 'true')) out.push(['satellite', 'the switch does not reach every map']);
    if (!document.querySelectorAll('#world .satg image').length) out.push(['satellite', 'imagery tiles are not requested on the main map']);
    Q.satSet(false);
    try { localStorage.removeItem('kansai-sat'); } catch (e) {}
    Q.hold(false);
    return out;
  });
  ia.forEach(([c, m]) => err(c, m));
  // field notes: every system draws; a photograph opens; every pair's table is reported (run.py recomputes it from the data)
  fnReport = await page.evaluate(async () => {
    const Q = window.__QA, out = { errors: [], tables: {}, prof: {}, strip: null }, wait = (ms) => new Promise((r) => setTimeout(r, ms));
    if (!Q.fnLoad) { out.errors.push('the field notes are not wired to the QA hooks'); return out; }
    const ok = await Q.fnLoad(); if (!ok) { out.errors.push('the field-notes map did not build'); return out; }
    const F = Q.fn;
    for (const k of Object.keys(Q.FNSYS)) {
      F.setSys(k, true); await wait(60);
      const shown = [...document.querySelectorAll('#fnmap svg.fn-svg > g > g')].filter((g) => g.style.display !== 'none' && g.querySelector('path')).length;
      if (!shown) out.errors.push(`system ${k} draws nothing`);
      if (!document.querySelectorAll('#fnleg li').length) out.errors.push(`system ${k} has no legend`);
      const pressed = document.querySelector(`.fnchip[data-fs="${k}"]`);
      if (!pressed || pressed.getAttribute('aria-pressed') !== 'true') out.errors.push(`the chip of system ${k} does not show it is on`);
    }
    F.setSys('ride', true); await wait(60);
    F.openPhoto(0); await wait(60);
    const card = document.querySelector('#fnmap .mcard'), img = card && card.querySelector('img');
    if (!card || card.hidden || !img || !/img\/field\//.test(img.getAttribute('src'))) out.errors.push('a photograph does not open in its card');
    F.closePhoto();
    const vi = F.D.town.photos.findIndex((q) => q.video);
    if (vi >= 0) {
      F.openPhoto(vi); await wait(60);
      const v = card.querySelector('video'), cap = card.querySelector('figcaption');
      if (!v || !/^img\/field\/\d{8}_\d{6}\.mp4$/.test(v.getAttribute('src') || '') || !v.controls || !v.hasAttribute('playsinline')) out.errors.push('a video does not open in its card with controls');
      else if (card.scrollHeight > card.clientHeight + 1 || cap.getBoundingClientRect().bottom > card.getBoundingClientRect().bottom + 1) out.errors.push('a video card hides its caption below the fold');
      F.closePhoto();
    }
    const fc = F.cam(); F.zoom(1e4, fc.W / 2, fc.H / 2); await wait(20);
    const fb = document.querySelector('#fnmap .msb'), fr = fb && fb.querySelector('rect');
    if (!fr || +fr.getAttribute('width') > +fb.getAttribute('width') || +fr.getAttribute('width') < 20) out.errors.push(`the scale bar at full zoom is ${fr && fr.getAttribute('width')} px in a ${fb && fb.getAttribute('width')} px box`);
    for (const pair of Object.keys(F.D.region.options)) {
      document.querySelector(`#fnopts .fnpair[data-pair="${pair}"]`).click(); await wait(80);
      out.tables[pair] = [...document.querySelectorAll('#fnopts tbody tr')].map((tr) => [...tr.children].map((td) => td.textContent.trim()));
      const sv = document.getElementById('fnprof');
      out.prof[pair] = { ve: sv.getAttribute('data-ve'), last: [...sv.querySelectorAll('text')].map((t) => t.textContent).pop() };
    }
    const sp = document.getElementById('fnprof'), r = sp.getBoundingClientRect();
    sp.dispatchEvent(new MouseEvent('mousemove', { clientX: r.left + r.width * 0.5, clientY: r.top + r.height * 0.5, bubbles: true })); await wait(40);
    const cur = document.querySelector('#fnmap .fcur');
    if (!cur || cur.style.display === 'none') out.errors.push('a point on the route profile does not light on the map');
    sp.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true })); await wait(20);
    out.strip = document.getElementById('fnstrip').getAttribute('data-ve');
    document.querySelector('#fnopts .fnpair[data-pair="hongu-hayatama"]').click(); await wait(40);
    F.setSys('ride', true);
    return out;
  });
  fnReport.errors.forEach((m) => err('fieldnotes', m));
  // tile placement samples: run.py re-projects the same corners with kansai/qa/tm.py
  tiles = await page.evaluate(() => {
    const Q = window.__QA, out = [], F = Q.frame;
    const probes = [[F[0] + 5, F[1] + 5], [F[2] - 5, F[3] - 5], [(F[0] + F[2]) / 2, (F[1] + F[3]) / 2], [690, 805]];
    for (let z = Q.TILESETS.sat.z[0]; z <= Q.TILESETS.sat.z[1]; z++) probes.forEach((q) => {
      const ll = Q.invTM(q[0], q[1]), n = Math.pow(2, z), x = Math.floor((ll[0] + 180) / 360 * n), r = ll[1] * Math.PI / 180;
      const y = Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n);
      out.push({ z, x, y, m: Q.tileMatrix(x, y, z) });
    });
    return out;
  });
  links = await page.evaluate(() => [...document.querySelectorAll('a[href^="http"]')].map((a) => ({
    href: a.href, text: a.textContent.replace(/\s+/g, ' ').trim(), cls: a.className,
    block: (a.closest('li, p, .pl, figcaption, .cap, td, div') || a).textContent.replace(/\s+/g, ' ').trim() })));
}

// 5. charts + diagrams: no text overflowing its SVG, colliding with other text, or spilling out of the box it sits in
async function chartChecks(pg, tag) {
  const out = await pg.evaluate(() => {
    const out = [];
    document.querySelectorAll('figure svg, #valley, .board svg, .pictos svg').forEach((svg, si) => {
      if (svg.closest('.mini, #mapwrap, .legend, #ksmap, #kmkmap, #fnmap, .klegend') || svg.classList.contains('msb') || svg.classList.contains('pg')) return;
      const vb = svg.viewBox && svg.viewBox.baseVal; if (!vb || !vb.width) return;
      const texts = [...svg.querySelectorAll('text')].filter((t) => t.textContent.trim() && t.getBBox().width > 0);
      const id = (svg.getAttribute('aria-label') || svg.closest('figure, section, div')?.id || 'svg#' + si).slice(0, 70);
      const boxes = texts.map((t) => { const b = t.getBBox(); return { t: t.textContent.trim(), x: b.x, y: b.y, w: b.width, h: b.height, el: t }; });
      boxes.forEach((b) => {
        if (b.x < vb.x - 1 || b.y < vb.y - 1 || b.x + b.w > vb.x + vb.width + 1 || b.y + b.h > vb.y + vb.height + 1) out.push(['chart-overflow', `“${b.t}” spills outside the drawing`, id]);
      });
      for (let a = 0; a < boxes.length; a++) for (let b = a + 1; b < boxes.length; b++) {
        const A = boxes[a], B = boxes[b];
        const ox = Math.min(A.x + A.w, B.x + B.w) - Math.max(A.x, B.x), oy = Math.min(A.y + A.h, B.y + B.h) - Math.max(A.y, B.y);
        if (ox > 1 && oy > 0.3 * Math.min(A.h, B.h)) out.push(['chart-overlap', `“${A.t}” overlaps “${B.t}”`, id]);
      }
      // a label drawn in a box (a rect grouped with it, as in a diagram) must fit inside that box: the case that
      // broke the plan diagram. Bars and invisible hit areas are not boxes.
      boxes.forEach((b) => {
        const g = b.el.parentNode; if (!g || g === svg || g.tagName.toLowerCase() !== 'g') return;
        [...g.children].filter((r) => r.tagName.toLowerCase() === 'rect' && !r.classList.contains('khit') && getComputedStyle(r).stroke !== 'none').forEach((rEl) => {
          const r = rEl.getBBox(), ax = +b.el.getAttribute('x'), ay = +b.el.getAttribute('y');
          if (!(ax >= r.x && ax <= r.x + r.width && ay >= r.y && ay <= r.y + r.height)) return;
          if (b.x < r.x - 0.5 || b.x + b.w > r.x + r.width + 0.5 || b.y < r.y - 0.5 || b.y + b.h > r.y + r.height + 0.5)
            out.push(['text-in-box', `“${b.t}” spills out of its box (${b.w.toFixed(0)} wide in a ${r.width.toFixed(0)} box)`, id]);
        });
      });
    });
    return out;
  });
  out.forEach(([c, m, w]) => err(c, m, `${tag} · ${w}`));
}
await chartChecks(page, '1440px');

// 6. mini-maps stay inside the data frame
const minis = await page.evaluate(() => {
  const F = window.__QA ? window.__QA.frame : null, out = [];
  if (!F) return out;
  document.querySelectorAll('.mini svg.m').forEach((s, i) => {
    const v = s.getAttribute('viewBox').split(/\s+/).map(Number), cap = s.closest('.mini')?.querySelector('figcaption')?.textContent.slice(0, 50) || 'mini ' + i;
    if (v[0] < F[0] - 0.05 || v[1] < F[1] - 0.05 || v[0] + v[2] > F[2] + 0.05 || v[1] + v[3] > F[3] + 0.05) out.push([cap, v.map((x) => +x.toFixed(1))]);
  });
  return out;
});
minis.forEach(([c, v]) => err('mini-frame', `mini-map view leaves the data frame ${JSON.stringify(v)}`, c));

// placeholders for evidence still to come (.todo): kept out of the inventory, reported to run.py
const todos = await page.evaluate(() => [...document.querySelectorAll('.todo')].map((e) => e.getAttribute('data-plan') || '?'));
// 7. text inventory: everything a reader can see or hear (prose, charts, map labels, tooltips, legends, aria)
const inv = await page.evaluate(() => {
  const out = [], Q = window.__QA, add = (src, t) => { if (t && /\S/.test(t)) out.push({ src, text: t.replace(/\s+/g, ' ').trim() }); };
  // .todo: an editorial placeholder for evidence still to come, not a claim; run.py reports it and fails a deploy while any remain
  const skip = (el) => el.closest('script, style, #scalebar, .msb, .zoomctl, .zc, noscript, title, desc, .todo');
  // one item per leaf block (a paragraph, a stat box, a chart label …), so claims can be matched whole
  const BLOCK = 'p, li, h1, h2, h3, h4, h5, h6, figcaption, .cap, td, th, dt, dd, blockquote, .stats > div, .chain .i, .mini figcaption > span, svg text, button, .viewname, .zhint, .attrib';
  const blocks = [...document.body.querySelectorAll(BLOCK)].filter((e) => !skip(e) && !e.querySelector(BLOCK));
  const inBlock = new Set(blocks);
  // a block that carries data-rk shows numbers of the risk analysis: run.py recomputes it from kansai/data/risk.js
  const srcOf = (e) => e.hasAttribute('data-rk') ? 'rk:' + e.getAttribute('data-rk') + '|' + (e.getAttribute('data-rkf') || '{:,}')
    : e.tagName.toLowerCase() + (e.closest('[id]') ? '#' + e.closest('[id]').id : '');
  blocks.forEach((e) => add(srcOf(e), e instanceof SVGElement ? e.textContent : (e.innerText || e.textContent)));
  // anything outside those blocks (loose text in divs) is collected per parent so nothing escapes the check
  const loose = new Map(), walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const p = n.parentElement; if (!p || skip(p) || !n.textContent.trim()) continue;
    const cb = p.closest(BLOCK); if (cb && inBlock.has(cb)) continue;
    loose.set(p, (loose.get(p) || '') + n.textContent);
  }
  loose.forEach((t, p) => add('loose:' + p.tagName.toLowerCase() + (p.closest('[id]') ? '#' + p.closest('[id]').id : ''), t));
  document.querySelectorAll('[aria-label]').forEach((e) => { if (!skip(e)) add('aria-label', e.getAttribute('aria-label')); });
  document.querySelectorAll('[title]').forEach((e) => add('title', e.getAttribute('title')));
  document.querySelectorAll('meta[name="description"], meta[property="og:description"]').forEach((e) => add('meta', e.getAttribute('content')));
  add('title-tag', document.title);
  if (Q) {
    Q.LABELS.forEach((l) => { add('map-label', l[1]); if (l[7]) add('map-tooltip', l[7]); });
    Object.values(Q.LEG).forEach((l) => l && add('legend', l[3])); Object.values(Q.GROUPLEG).forEach((g) => g.forEach((l) => add('legend', l[3])));
    Q.FACETS.forEach((f) => { add('facet', f.q); add('facet', f.r); add('facet', f.m); });
    Q.MEDIA.forEach((m) => { add('media', m.title.replace(/<[^>]+>/g, '')); if (m.text) add('media', m.text.replace(/<[^>]+>/g, ''));
      m.images.forEach((im) => { add('media', im.caption.replace(/<[^>]+>/g, '')); add('media-credit', im.credit.replace(/<[^>]+>/g, '')); add('media-alt', im.alt); }); });
    (Q.G.roadlabels || []).forEach((r) => add('road-label', r[3]));
    Object.values(Q.CLAB || {}).forEach((arr) => arr.forEach((c) => add('contour-label', c[3].toLocaleString('en') + ' m')));
    Q.KPLACES.forEach((p) => add('system-map', p[1]));
    Object.values(Q.KLEG || {}).forEach((l) => add('legend', l[2]));
    document.querySelectorAll('.step').forEach((s) => add('view-name', s.getAttribute('data-name')));
    if (Q.fn && Q.fn.D) {
      Q.fn.D.town.photos.forEach((p) => { add('fn-photo', p.cap.replace(/<[^>]+>/g, '')); });
      add('fn-photo-credit', 'Photo: the authors, field visit, 28 September 2025 · all rights reserved');
      Object.keys(Q.FNSYS).forEach((k) => (Q.FNSYS[k].leg || '').split(' ').forEach((l) => l && l !== 'ramp' && Q.FNLEG && Q.FNLEG[l] && add('legend', Q.FNLEG[l][2])));
    }
  }
  return out;
});
const usedPoints = hasQA ? await page.evaluate(() => {
  const Q = window.__QA, s = new Set();
  Q.LABELS.forEach((l) => s.add(l[0])); Q.MARKERS.forEach((m) => s.add(m[0])); Q.LINKS.forEach((l) => { s.add(l[0]); s.add(l[1]); });
  Q.FACETS.forEach((f) => (f.pts || []).forEach((p) => s.add(p[0])));
  Object.values(Q.HL).forEach((h) => (h.pts || []).forEach((p) => s.add(p)));
  Q.MEDIA.forEach((m) => s.add(m.pt)); Q.KPLACES.forEach((p) => s.add(p[0]));
  document.querySelectorAll('.step[data-edge]').forEach((st) => st.getAttribute('data-edge').split(/\s+/).forEach((k) => k && s.add(k)));
  return [...s];
}) : [];
if (shotsDir) {
  await page.evaluate(() => document.getElementById('after')?.scrollIntoView());
  await page.waitForTimeout(400);
  const el = await page.$('#after'); if (el) await el.screenshot({ path: `${shotsDir}/desktop_after.png` });
}
// ---------------------------------------------------------------- HTML text boxes: nothing may overflow its own box
async function htmlOverflow(pg, tag) {
  const bad = await pg.evaluate((sel) => [...document.querySelectorAll(sel)].filter((e) => e.offsetParent && e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 1)
    .map((e) => `“${e.textContent.trim().slice(0, 60)}” is ${e.scrollWidth - e.clientWidth}px wider than its box`), OVERFLOW_SEL);
  bad.forEach((b) => err('text-overflow', b, tag));
}
await htmlOverflow(page, '1440px');
await ctx.close();

// ---------------------------------------------------------------- every screen class the page promises to fit
for (const [w, h, name] of [[1920, 1080, 'desktop-large'], [1280, 800, 'laptop'], [1180, 820, 'tablet-landscape'], [1024, 768, 'tablet-1024'], [820, 1180, 'tablet-portrait']]) {
  const v = await open({ width: w, height: h });
  const tag = `${w}px`;
  await htmlOverflow(v.page, tag);
  await chartChecks(v.page, tag);
  const m2 = await v.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, map: document.getElementById('map')?.getBoundingClientRect() }));
  if (m2.sw > w + 1) err('viewport-overflow', `page is ${m2.sw}px wide on a ${w}px ${name} screen`, tag);
  if (!m2.map || m2.map.width < 280 || m2.map.height < 240) err('viewport-map', `map is ${m2.map && m2.map.width.toFixed(0)}×${m2.map && m2.map.height.toFixed(0)}px on a ${name} screen`, tag);
  // the map re-fits when the window changes size (rotation, split screen)
  const fitOk = await v.page.evaluate(async () => {
    const Q = window.__QA; if (!Q) return true; Q.hold(true); Q.activate(0); const k0 = Q.cam().k;
    return k0 > 0;
  });
  if (!fitOk) err('viewport-fit', 'camera did not fit the step view', tag);
  await v.page.setViewportSize({ width: Math.round(h), height: Math.round(w) });   // rotate
  await v.page.waitForTimeout(250);
  const rot = await v.page.evaluate(() => { const Q = window.__QA, c = Q.cam(), r = document.getElementById('map').getBoundingClientRect(); return { W: c.W, H: c.H, rw: r.width, rh: r.height, sw: document.documentElement.scrollWidth, iw: window.innerWidth }; });
  if (Math.abs(rot.W - rot.rw) > 2 || Math.abs(rot.H - rot.rh) > 2) err('viewport-resize', `after rotating, the map camera (${rot.W.toFixed(0)}×${rot.H.toFixed(0)}) does not match the map box (${rot.rw.toFixed(0)}×${rot.rh.toFixed(0)})`, tag);
  if (rot.sw > rot.iw + 1) err('viewport-overflow', `page is ${rot.sw}px wide after rotating to ${rot.iw}px`, tag);
  await v.ctx.close();
}
// ---------------------------------------------------------------- web fonts blocked: the fallback serif is wider, nothing may spill
for (const [w, h] of [[1440, 900], [390, 844]]) {
  const f = await open({ width: w, height: h }, { noFonts: true });
  await htmlOverflow(f.page, `${w}px fallback-font`);
  await chartChecks(f.page, `${w}px fallback-font`);
  await f.ctx.close();
}

// ---------------------------------------------------------------- mobile pass
const m = await open({ width: 390, height: 844 });
const mob = await m.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth,
  map: (document.getElementById('map')?.getBoundingClientRect().height) || 0 }));
if (mob.sw > mob.iw + 1) err('mobile-overflow', `page is ${mob.sw}px wide on a ${mob.iw}px phone (sideways scroll)`);
if (mob.map < 200) err('mobile-map', `map is only ${mob.map}px tall on a phone`);
await htmlOverflow(m.page, '390px');
await chartChecks(m.page, '390px');
if (hasQA) await stepChecks(m.page, 'mobile');
await m.ctx.close();
await browser.close();

writeFileSync(reportPath, JSON.stringify({ errors, warnings, inventory: inv, usedPoints, tiles, links, fn: fnReport, todos }, null, 1));
console.log(`render QA: ${errors.length} error(s), ${warnings.length} warning(s), ${inv.length} text items`);
