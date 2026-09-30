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
if (shotsDir) mkdirSync(shotsDir, { recursive: true });
const url = pathToFileURL(resolve(pagePath)).href;
const errors = [], warnings = [];
const err = (check, msg, where = '') => errors.push({ check, msg, where });
const warn = (check, msg, where = '') => warnings.push({ check, msg, where });

const browser = await chromium.launch();

async function open(viewport) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const cache = process.env.QA_FONT_CACHE;
  if (cache) {
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
  page.on('console', (m) => { if (m.type() === 'error') err('console-error', m.text(), viewport.width + 'px'); });
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  return { ctx, page };
}

// ---------------------------------------------------------------- desktop pass
const { ctx, page } = await open({ width: 1440, height: 900 });
const hasQA = await page.evaluate(() => !!window.__QA);
if (!hasQA) { err('qa-hook', 'window.__QA missing — page script failed or hook removed'); }

// 1. references: every attribute/key the page uses must resolve to data
if (hasQA) {
  const refs = await page.evaluate(() => {
    const Q = window.__QA, out = [], G = Q.G, words = (s) => (s || '').split(/\s+/).filter(Boolean);
    const groups = new Set(Q.groups), layers = new Set(Q.layers);
    document.querySelectorAll('.step').forEach((s, i) => {
      const v = s.getAttribute('data-view'); if (!G.views[v]) out.push(['view', `step ${i}: data-view "${v}" not in GEO.views`]);
      words(s.getAttribute('data-on')).forEach((n) => { if (!layers.has(n)) out.push(['layer', `step ${i}: data-on "${n}" has no layer`]); });
      words(s.getAttribute('data-overlay')).forEach((n) => { if (!groups.has(n)) out.push(['overlay', `step ${i}: data-overlay "${n}" has no labels/markers`]); });
      words(s.getAttribute('data-legend')).forEach((n) => { if (n !== 'tsd' && !Q.LEG[n]) out.push(['legend', `step ${i}: data-legend "${n}" not in LEG`]); });
      if (!s.getAttribute('data-name')) out.push(['view', `step ${i}: missing data-name`]);
    });
    Q.LABELS.forEach((l) => { if (!Q.ptOf(l[0])) out.push(['point', `label "${l[1]}" → unknown point "${l[0]}"`]); });
    Q.MARKERS.forEach((m) => { if (!Q.ptOf(m[0])) out.push(['point', `marker ${m[1]} → unknown point "${m[0]}"`]); });
    Q.LINKS.forEach((l) => { if (!Q.ptOf(l[0]) || !Q.ptOf(l[1])) out.push(['point', `link ${l[0]}→${l[1]} unresolved`]); });
    Q.FACETS.forEach((f, i) => {
      (f.layers || []).forEach((l) => { if (!G.layers[l[0]]) out.push(['layer', `facet ${i} "${f.q}": layer "${l[0]}" missing`]); });
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
    await pg.evaluate((i) => document.querySelectorAll('.step')[i].scrollIntoView({ block: 'center' }), i);
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
      const hiddenKey = hiddenEls.filter((t) => t.classList.contains('key')).map((t) => t.textContent);
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
      return { name: s.getAttribute('data-name'), inFrame: vis[0] >= F[0] - eps && vis[1] >= F[1] - eps && vis[2] <= F[2] + eps && vis[3] <= F[3] + eps,
        vis, seen, overlaps, outside, hidden, hiddenKey, off, legend: legendItems, wantLegend: !!(s.getAttribute('data-legend') || '').trim(), nlabels: labs.length };
    }, i);
    const where = `${tag} step ${i} “${r.name}”`;
    if (!r.inFrame) err('camera-frame', `view shows area outside the data frame ${JSON.stringify(r.vis.map((v) => +v.toFixed(1)))}`, where);
    if (r.seen < 0.6) warn('camera-crop', `only ${(r.seen * 100).toFixed(0)}% of the step’s view is on screen`, where);
    r.overlaps.forEach((o) => err('label-overlap', o, where));
    r.outside.forEach((o) => err('label-outside', o, where));
    r.off.forEach((o) => err('layer-off', `data-on layer "${o}" not switched on`, where));
    if (r.wantLegend && !r.legend) err('legend-empty', 'legend requested but empty', where);
    if (r.hidden.length) warn('label-hidden', `${r.hidden.length} label(s) hidden by declutter: ${r.hidden.join(' | ')}`, where);
    // labels the text refers to (class "key") must be readable at the step's own view on desktop; phones can zoom
    if (r.hiddenKey.length) (tag === 'desktop' ? err : warn)('key-label-hidden', `label(s) the text relies on are hidden: ${r.hiddenKey.join(' | ')}`, where);
    if (shotsDir) { await pg.waitForTimeout(900); await pg.screenshot({ path: `${shotsDir}/${tag}_${String(i).padStart(2, '0')}.png` }); }  // let the 0.7 s layer fade finish
  }
}
if (hasQA) await stepChecks(page, 'desktop');

// 4. zoom controls: in / out / reset, clamps, wheel + drag
if (hasQA) {
  await page.evaluate(() => { window.__QA.hold(false); document.querySelectorAll('.step')[0].scrollIntoView({ block: 'center' }); });
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
    const kMaxHit = Q.cam().k;
    btn('reset').click(); await wait(1500);
    const s = Q.stepCam(), c = Q.cam();
    return { k0, kIn, kOut: cOut.k, kMin: Q.kMin(), outInFrame, kMaxHit, K_MAX: Q.K_MAX, cam: c, step: s,
      reset: Math.abs(c.k - s.k) < 1e-6 * s.k && Math.abs(c.cx - s.cx) < 1e-3 && Math.abs(c.cy - s.cy) < 1e-3 };
  });
  if (!(z.kIn > z.k0 * 1.5 || z.k0 * 1.6 > z.K_MAX)) err('zoom', `zoom-in did not zoom (k ${z.k0} → ${z.kIn})`);
  if (Math.abs(z.kOut - z.kMin) > 1e-9) err('zoom', `zoom-out does not stop at the frame (k ${z.kOut}, kMin ${z.kMin})`);
  if (!z.outInFrame) err('zoom', 'zoomed-out view leaves the data frame');
  if (Math.abs(z.kMaxHit - z.K_MAX) > 1e-9) err('zoom', `zoom-in does not clamp at K_MAX (${z.kMaxHit})`);
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

// 5. charts + diagrams: no text overflowing its SVG, no text colliding with other text
const charts = await page.evaluate(() => {
  const out = [];
  document.querySelectorAll('figure svg, #valley svg, .board svg, .pictos svg').forEach((svg, si) => {
    if (svg.closest('.mini, #mapwrap, .legend') || svg.classList.contains('msb') || svg.classList.contains('pg')) return;
    const vb = svg.viewBox && svg.viewBox.baseVal; if (!vb || !vb.width) return;
    const texts = [...svg.querySelectorAll('text')].filter((t) => t.textContent.trim() && t.getBBox().width > 0);
    const id = (svg.getAttribute('aria-label') || svg.closest('figure, section, div')?.id || 'svg#' + si).slice(0, 70);
    const boxes = texts.map((t) => { const b = t.getBBox(); return { t: t.textContent.trim(), x: b.x, y: b.y, w: b.width, h: b.height }; });
    boxes.forEach((b) => {
      if (b.x < vb.x - 1 || b.y < vb.y - 1 || b.x + b.w > vb.x + vb.width + 1 || b.y + b.h > vb.y + vb.height + 1) out.push(['chart-overflow', `“${b.t}” spills outside the drawing`, id]);
    });
    for (let a = 0; a < boxes.length; a++) for (let b = a + 1; b < boxes.length; b++) {
      const A = boxes[a], B = boxes[b];
      const ox = Math.min(A.x + A.w, B.x + B.w) - Math.max(A.x, B.x), oy = Math.min(A.y + A.h, B.y + B.h) - Math.max(A.y, B.y);
      if (ox > 1 && oy > 0.3 * Math.min(A.h, B.h)) out.push(['chart-overlap', `“${A.t}” overlaps “${B.t}”`, id]);
    }
  });
  return out;
});
charts.forEach(([c, m, w]) => err(c, m, w));

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

// 7. text inventory: everything a reader can see or hear (prose, charts, map labels, tooltips, legends, aria)
const inv = await page.evaluate(() => {
  const out = [], Q = window.__QA, add = (src, t) => { if (t && /\S/.test(t)) out.push({ src, text: t.replace(/\s+/g, ' ').trim() }); };
  const skip = (el) => el.closest('script, style, #scalebar, .msb, .zoomctl, .zc, noscript, title, desc');
  // one item per leaf block (a paragraph, a stat box, a chart label …), so claims can be matched whole
  const BLOCK = 'p, li, h1, h2, h3, h4, h5, h6, figcaption, .cap, td, th, dt, dd, blockquote, .stats > div, .chain .i, .mini figcaption > span, svg text, button, .viewname, .zhint, .attrib';
  const blocks = [...document.body.querySelectorAll(BLOCK)].filter((e) => !skip(e) && !e.querySelector(BLOCK));
  const inBlock = new Set(blocks);
  blocks.forEach((e) => add(e.tagName.toLowerCase() + (e.closest('[id]') ? '#' + e.closest('[id]').id : ''), e instanceof SVGElement ? e.textContent : (e.innerText || e.textContent)));
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
    Object.values(Q.LEG).forEach((l) => l && add('legend', l[3])); Q.TSD.forEach((l) => add('legend', l[3]));
    Q.FACETS.forEach((f) => { add('facet', f.q); add('facet', f.r); add('facet', f.m); });
    document.querySelectorAll('.step').forEach((s) => add('view-name', s.getAttribute('data-name')));
  }
  return out;
});
const usedPoints = hasQA ? await page.evaluate(() => {
  const Q = window.__QA, s = new Set();
  Q.LABELS.forEach((l) => s.add(l[0])); Q.MARKERS.forEach((m) => s.add(m[0])); Q.LINKS.forEach((l) => { s.add(l[0]); s.add(l[1]); });
  Q.FACETS.forEach((f) => (f.pts || []).forEach((p) => s.add(p[0])));
  return [...s];
}) : [];
if (shotsDir) {
  await page.evaluate(() => document.getElementById('after')?.scrollIntoView());
  await page.waitForTimeout(400);
  const el = await page.$('#after'); if (el) await el.screenshot({ path: `${shotsDir}/desktop_after.png` });
}
// ---------------------------------------------------------------- HTML text boxes: nothing may overflow its own box
const OVERFLOW_SEL = '.picto-row figcaption, .stats > div, .chain .i, .board p, figcaption, .legend span, td, th, button, .viewname, .mini figcaption span';
async function htmlOverflow(pg, tag) {
  const bad = await pg.evaluate((sel) => [...document.querySelectorAll(sel)].filter((e) => e.offsetParent && e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 1)
    .map((e) => `“${e.textContent.trim().slice(0, 60)}” is ${e.scrollWidth - e.clientWidth}px wider than its box`), OVERFLOW_SEL);
  bad.forEach((b) => err('text-overflow', b, tag));
}
await htmlOverflow(page, '1440px');
await ctx.close();

{
  const mid = await open({ width: 1024, height: 768 });
  await htmlOverflow(mid.page, '1024px');
  const sw = await mid.page.evaluate(() => document.documentElement.scrollWidth);
  if (sw > 1025) err('tablet-overflow', `page is ${sw}px wide on a 1024px screen`);
  await mid.ctx.close();
}

// ---------------------------------------------------------------- mobile pass
const m = await open({ width: 390, height: 844 });
const mob = await m.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth,
  map: (document.getElementById('map')?.getBoundingClientRect().height) || 0 }));
if (mob.sw > mob.iw + 1) err('mobile-overflow', `page is ${mob.sw}px wide on a ${mob.iw}px phone (sideways scroll)`);
if (mob.map < 200) err('mobile-map', `map is only ${mob.map}px tall on a phone`);
await htmlOverflow(m.page, '390px');
if (hasQA) await stepChecks(m.page, 'mobile');
await m.ctx.close();
await browser.close();

writeFileSync(reportPath, JSON.stringify({ errors, warnings, inventory: inv, usedPoints }, null, 1));
console.log(`render QA: ${errors.length} error(s), ${warnings.length} warning(s), ${inv.length} text items`);
