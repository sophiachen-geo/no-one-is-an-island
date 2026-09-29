# No One Is an Island

An interactive force-directed map of geography travel stories.
Click an island to read fragments. Filter by tag to find connections across archipelagos.

## Setup

```bash
npm install
npm run dev
```

Open http://localhost:5173/no-one-is-an-island/

## Add a Fragment

Create a `.md` file in `src/content/fragments/`. Minimum required fields:

```yaml
---
title: Your Title Here
places: [place-id]
tags: [tag1, tag2, tag3]
---

Your writing here.
```

## Deploy to GitHub Pages

```bash
npm run deploy
```

Then in your GitHub repo: Settings → Pages → Source: `gh-pages` branch.

## Place IDs (Fall 2025 Trip)

| Setouchi | Okinawa | Matsu | Hong Kong | Fujian |
|---|---|---|---|---|
| naoshima | okinawa | nangan | lantau-muiwo | meizhou |
| shodoshima | | beigan | cheung-chau | gulangyu |
| honjima | | dongju | sai-kung | |
| | | xiju | yim-tin-tsai | |
| | | | lamma | |
| | | | ap-lei-chau | |
| | | | aberdeen | |
| | | | ma-wan | |

## Kansai subpage

`kansai/index.html` — 新宮 Shingū: one small city planned at six overlapping scales (regional centre,
polycentric compact city, hazard-filtered zoning, pre-disaster reconstruction, the three-prefecture Kumano
basin, the pilgrimage landscape). A self-contained static page served at `/no-one-is-an-island/kansai/`.
Its map data is generated offline from MLIT 国土数値情報, OpenStreetMap and SRTM by the scripts in
`kansai/tools/` (see `kansai/tools/README.md`).
