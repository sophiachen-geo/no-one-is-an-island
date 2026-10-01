# Kamikura field kit · comparing gazes

For the まなざし (gaze) layer of the Kamikura chapter and the parts of the study that need fieldwork: the
photographic comparison, the bridge census and the route sequences. Send material as described at the end; the page
is built from it.

## The precedent: Gou & Shibata

Gou, S. & Shibata, S. (2017). Using visitor-employed photography to study the visitor experience on a pilgrimage
route: a case study of the Nakahechi Route on the Kumano Kodo pilgrimage network. *Journal of Outdoor Recreation and
Tourism* 18: 22–33 (doi:10.1016/j.jort.2017.01.006, closed access). The same study is chapter 6 (pp. 124–153) of
Gou's open-access Kyoto University thesis (2017, doi:10.14989/doctor.k20542). The details below come from the thesis.

| | what they did |
|---|---|
| route, dates | the last 6.9 km of the Nakahechi, 発心門王子 → 本宮大社; 21 fine days, June–September 2014 |
| participants | 16 people approached at the trailhead were given cameras, balanced by age and gender (main group); 15 shared the photos from their own cameras after the walk (control group); 631 photos (479 + 152) |
| instruction | photograph "any scenes or features that contributed to [your] walking experience"; no limit on the number; reasons were collected in interviews afterwards |
| location | no GPS: researchers placed each viewpoint on 2011 aerial photographs. The route was cut into 132 segments of 50.22 m and into 10 sections by adjacent land use (forest / village) |
| coding | 14 categories built inductively (a photo may take two). Breadth of view after De Veer & Burrough (1978): intraocular < 150 m, ocular 150–1,500 m, extraocular > 1,500 m |
| analysis | category shares per respondent, compared between groups (t-tests); clustering of each view type along the route (index of dispersion per segment against a Poisson distribution) |
| interviews | 28 semi-structured, after the walk: why each photo, prior image of the route, the strongest impression; open-coded |
| findings | Statue & Symbol 19%, Terrain 18%, Path 17%, Village 11% of photos per respondent; ordinary elements carry the experience; wide views cluster at villages and at the one official lookout |
| limits | stated: few respondents; photographing may change what people notice (hence the control group). Not reported: camera, who coded, inter-coder agreement. The thesis has no DEM, viewshed or slope analysis; "topography" is interpretation |

## The adaptation: six gazes, one coding frame

The question changes from what visitors find worth photographing to who looks at the mountain foot, and what each
gaze selects or leaves out.

| gaze | whose | how to collect |
|---|---|---|
| visitor | people walking to or from 神倉神社 | Gou & Shibata's instruction verbatim; phone camera with location and compass on; a 10-minute interview after the walk |
| resident | people living in 千穂 and 神倉 | the same procedure; instruction: "photograph the places that make this neighbourhood what it is for you" |
| researcher | you, systematically | every 25 m along the transect and along the lane at the foot: one frame ahead, one toward the mountain (walking or by bicycle, the same both ways) |
| promotional | city, tourism association, JR, guidebooks | every published image of the Kamikura foot, with URL or source and date |
| historical | Kubo Photo Studio, 『熊野百景写真帖』 (1913; NDL, public domain) and later albums | images of Kamikura and the foot, with catalogue number |
| municipal | plans and hazard maps | images and maps of the area in the master plan, the disaster plan and the hazard maps |

Every image is coded the same way:
- **what**: Gou & Shibata's categories first, new ones added only when needed;
- **layer**: 下部構造 ground, 中部構造 lots, 上部構造 buildings and open space, 流れ flows, まなざし signs, maps and views;
- **breadth of view**: < 150 m, 150–1,500 m, > 1,500 m;
- **position and facing**: from the photo's EXIF where present, otherwise placed on the map;
- **distance from the mountain foot**: computed from the page's foot line (upslope, 0–25 m, 25–50 m, …).

The last field ties the gaze to the measured morphology. Does the visitor gaze gather at the threshold (the steps,
the bridge), and the resident gaze along the lanes and the channel?

Comparisons:
- category shares by gaze (contingency test, or permutation);
- clustering per 25 m segment (index of dispersion, as Gou & Shibata);
- facing directions (circular statistics: toward the mountain, along the foot, toward the town);
- what each gaze omits: categories present in the researcher's systematic record but absent from a given gaze.

## Desk coding so far (1 October 2026)

`gazes.csv` holds the gazes that need no participants, coded by the frame above: 37 images from six publishers'
pages (34 photographic images and 3 maps or diagrams), 4 from the city's 2012 master plan, 1 plate from the 1913 album and
our 10 photographs at the foot. Columns: `position` (mountain, threshold, foot, town; `map` for maps and diagrams),
`town` (the town spread out in the frame as a view; houses seen at street level do not count), `breadth`, `category_1`/`category_2` (Gou & Shibata's, plus Channel),
`festival`. The page's comparison is built from it (`tools/kamikura/gazes.py`). One coder so far: a second coder on
the same images, and the visitor and resident gazes, are the next steps.

## Ethics

- Participants sign a short consent form, and their photos are used only with it.
- No recognisable faces of non-participants (blur them).
- No legible house numbers or name plates of private homes.
- Historical and promotional images are linked and cited. Only public-domain or openly licensed ones are shown.

## How to send material

- **Photos**: original files, with EXIF location and direction kept.
  - File name: `YYYYMMDD_HHMMSS_<gaze>_<participant>_<nn>.jpg`.
  - One row each in `photo_log.csv`.
  - Attach them in the chat or push them to `kansai/field/photos/`.
- **GPS tracks**: GPX from any phone app, one per walk or ride.
- **Bridge census**: `bridges.csv` lists the 7 crossings of the channel that OpenStreetMap maps (B01–B07, north to south).
  - Add footbridges to private houses as B08, B09, …
  - Photograph each crossing from upstream and from its deck.
  - Note name and date plates (橋名板), width, deck, railing, and whether it serves a house, a lane or a street.
- **Phone map**: `kamikura_field.gpx` holds the crossings, the transect and the mountain foot (median of the four definitions).
