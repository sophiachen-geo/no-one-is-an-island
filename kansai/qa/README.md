# Kansai QA/QC gate

Nothing on `kansai/index.html` reaches the live site unless this gate passes. It runs on every pull
request that touches `kansai/` (`.github/workflows/kansai-qa.yml`) and again before each GitHub Pages
deploy (`deploy.yml` needs it). A failed gate blocks the publish, so the live site keeps its last good version.

```bash
python3 kansai/qa/run.py                   # full gate (needs node + `npm i playwright`)
python3 kansai/qa/run.py --write-caveats   # after editing register.toml / points.toml
python3 kansai/qa/selftest.py              # proves the gate still catches planted faults
python3 kansai/qa/verify_points.py         # re-check map points against OpenStreetMap (network)
```

## What is checked

| Layer | Check | Fails when |
|---|---|---|
| Claims | `register.toml` | a number (digits or number words) is visible, audible (aria) or in a tooltip without a registered claim; a claim's text is no longer on the page; a claim lacks a source or a note |
| Derived numbers | `check =` in the register | a share, area, length, distance, sum or model statistic recomputed from the page's own data no longer matches the text |
| Map points | `points.toml` | a drawn point is further than its tolerance from an independently sourced coordinate (OSM, GSI, MLIT, Wikipedia/ダム便覧), or has no reference |
| Data | GEO block | a layer does not parse, a view or point leaves the frame, or the projection origin disagrees with the QA's own Gauss–Krüger code |
| Rendering | `check_render.mjs` (Chromium) | a JS error; a step's view, layer, overlay or legend is missing; land fill does not render; a view shows area outside the data; map labels collide or leave the frame; a label the text relies on (`key`) is hidden on desktop; chart text overlaps or spills; HTML text overflows its box (1440 / 1024 / 390 px); zoom in/out/reset, ctrl-wheel or drag misbehave; the phone layout scrolls sideways |
| Caveats | `CAVEATS.md` | the file differs from what the register generates |
| The gate | `selftest.py` | a planted fault (unsourced number, edited claim, stale statistic, moved point, render error, edited caveats) is not caught |

## Claim statuses

- `verified`: checked against the cited source.
- `corrected`: the draft differed from the source, and the page now follows the source. Listed in CAVEATS.md.
- `derived`: computed here from cited data, and recomputed on every run.
- `method`: a parameter of this repo's own analysis or drawing.
- `approximate`: verified, but rounded or simplified on the page. Listed in CAVEATS.md.
- `author`: from the author's text and not yet checked against a source. Listed in CAVEATS.md.

## Adding or changing text

1. Edit the page.
2. Run `python3 kansai/qa/run.py`. Every new number shows up as `unsourced-number` with its context.
3. Add a `[[claim]]` for it in `register.toml`, with the exact rendered text, a status, and a source or URL.
   Add a `check` if the number can be recomputed from the page's data.
4. New map point? Add it to `points.toml` with a coordinate from a source other than the one used to draw it.
5. Run `python3 kansai/qa/run.py --write-caveats` and commit `CAVEATS.md` with the change.

The gate cannot tell whether a cited source is itself right. The status field and CAVEATS.md make
that dependence explicit instead of hiding it.
