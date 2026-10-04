"""Rebuild kansai/index.html as a prologue and six themes (kansai/SHINGU.md), from main's page.

    git show origin/main:kansai/index.html > /tmp/main.html
    python3 kansai/tools/six/six.py /tmp/main.html kansai/index.html

Every existing block keeps its text; it only moves. New text is the theme heads, part heads, conclusions,
cross-references and the placeholders (.todo) for evidence the page does not hold yet."""
import re, sys
from pathlib import Path
from blocks import find, get, inner, children, attr, tagname
import texts as T

SRC, OUT = sys.argv[1], sys.argv[2]
s = open(SRC, encoding="utf-8").read()
plain = lambda e: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", e))


def rep1(t, old, new):
    assert t.count(old) == 1, old[:60]
    return t.replace(old, new)

# ------------------------------------------------------------------ the region that is rebuilt: contents pane → end of #after
a0, _ = find(s, r'<nav class="toc" id="contents"')
_, a1 = find(s, r'<section class="after" id="after">')
head, region, tail = s[:a0], s[a0:a1], s[a1:]

intro = get(region, r'<section class="topsec" id="intro"')
board = get(region, r'<section class="board" id="finding"')
hint = get(region, r'<p class="scroll-hint">')
stage = get(region, r'<main class="stage" id="stage">')
after = get(region, r'<section class="after" id="after">')

# ------------------------------------------------------------------ steps, by name
mapcol = get(stage, r'<div class="mapcol">')
steps = {attr(c, "data-name"): c for c in children(inner(get(stage, r'<div class="steps" id="steps">'))) if tagname(c) == "article"}
assert len(steps) == 33, len(steps)
used = set()

# 3G: the full exposure table leaves the pathways step for a step of its own, collapsed under its main results
# (the plan: “full table = audit trail”; the chart's numbers are bound to kansai/data/risk.js like the table's)
import json
KANSAI = str(Path(__file__).resolve().parents[2]) + "/"     # kansai/, for its data and pictures
_rk = open(KANSAI + "data/risk.js", encoding="utf-8").read().strip()
TIERS = json.loads(_rk[_rk.index("=") + 1:].rstrip(";"))["stats"]["tiers"]


def tier_chart():
    X0, W = 170, 190
    tot = TIERS["Shingu"]["total"]["people"]
    rows = [("all residents", "total", "#57555b", ".25"), ("tsunami, frequent class", "ts_l1", "#4a0f2f", "1"),
            ("tsunami, maximum class", "ts_max", "#8a2b5f", ".75"), ("river flood, planned scale", "fl_l1", "#2f5f94", ".8"),
            ("river flood, maximum", "fl_l2", "#4781c7", ".75"), ("any hazard zone", "u_all", "#57555b", ".75")]
    out = ['<text x="0" y="12" class="s">residents of Shingū, by hazard tier</text>']
    for i, (lab, k, col, op) in enumerate(rows):
        v = TIERS["Shingu"][k]["people"]; w = max(1.5, W * v / tot); y = 22 + 20 * i
        out.append(f'<text x="0" y="{y + 10}">{lab}</text><rect x="{X0}" y="{y}" width="{w:.1f}" height="12" fill="{col}" fill-opacity="{op}"/>'
                   f'<text x="{X0 + w + 4:.1f}" y="{y + 10}" data-rk="tiers.Shingu.{k}.people">{v:,}</text>')
    out.append('<text x="0" y="156" class="s">share aged 65 and over</text>')
    out.append('<rect x="0" y="163" width="10" height="8" fill="#57555b" fill-opacity=".35"/><text x="14" y="171" class="s">all residents</text>'
               '<rect x="100" y="163" width="10" height="8" fill="#1f4f86"/><text x="114" y="171" class="s">where floods can sweep houses away</text>')
    for i, (town, key) in enumerate((("Shingū", "Shingu"), ("Kihō", "Kiho"))):
        top = 182 + 28 * i
        out.append(f'<text x="0" y="{top + 15}">{town}</text>')
        for j, (k, col, op) in enumerate((("total", "#57555b", ".35"), ("collapse", "#1f4f86", "1"))):
            pc = TIERS[key][k]["pct65"]; w = W * pc / 100; y = top + 12 * j
            out.append(f'<rect x="{X0}" y="{y}" width="{w:.1f}" height="10" fill="{col}" fill-opacity="{op}"/>'
                       f'<text x="{X0 + w + 4:.1f}" y="{y + 9}" data-rk="tiers.{key}.{k}.pct65" data-rkf="{{:.0f}}%">{pc:.0f}%</text>')
    return ('            <figure class="fig chart">\n              <svg viewBox="0 0 400 240" role="img" aria-label="Residents of Shingū in each hazard tier, '
            'and the share aged 65 and over in Shingū and Kihō">\n                ' + "\n                ".join(out) + "\n              </svg>\n"
            '              <figcaption>Census residents fitted to the homes they live in; bars to scale. The full table adds Kihō’s tiers, '
            'the depths and durations and the landslide zones.</figcaption>\n            </figure>\n')


fd = steps["Four directions of risk"]
p_freq = re.search(r'\s*<p>Read by frequency, the pathways separate.*?</p>', fd, re.S)
f_tiers = re.search(r'\s*<figure class="fig">\s*<table class="tiers">.*?</figure>', fd, re.S)
p_age = re.search(r'\s*<p>Residents aged 65 and over are 37%.*?</p>', fd, re.S)
assert p_freq and f_tiers and p_age
for m in (p_freq, f_tiers, p_age):
    fd = rep1(fd, m.group(0), "")
steps["Four directions of risk"] = fd
g_tag = rep1(rep1(re.match(r"<article [^>]*>", fd).group(0), 'data-name="Four directions of risk"', 'data-name="Residents by hazard tier"'),
             'data-overlay="pathways"', 'data-overlay=""')
steps["Residents by hazard tier"] = (g_tag + '\n          <div class="card">\n            ' + p_freq.group(0).strip() + "\n" + tier_chart()
                                     + "            " + p_age.group(0).strip() + "\n"
                                     + '            <details class="methods"><summary>The full exposure table · every tier, Shingū and Kihō</summary>\n              '
                                     + f_tiers.group(0).strip() + "\n            </details>\n          </div>\n        </article>")

# references that the new order turns around
steps["Interventions along one system"] = rep1(steps["Interventions along one system"], "The valley section further down places each intervention",
                                              'The <a href="#kumano-system">valley section in the prologue</a> places each intervention')


def st(*names):
    out = ""
    for n in names:
        out += "        " + steps[n] + "\n\n"; used.add(n)
    return out


# ------------------------------------------------------------------ the prologue: glance (cut), the Kumano system
ic = children(inner(intro))
glance, ksys_h2, ksys_p, ksys = ic
cut_p = re.search(r"\s*<p>The name, “new shrine”, belongs to Kumano Hayatama Taisha.*?</p>", glance, re.S)
assert cut_p, "glance paragraph 3"
glance = glance.replace(cut_p.group(0), "")
for img in ("img/sato_haruo_museum.jpg", "img/nishimura_house.jpg"):
    m = re.search(r'\s*<figure class="fig photo"><img src="%s".*?</figure>' % re.escape(img), glance, re.S)
    assert m, img
    glance = glance.replace(m.group(0), "")
for lk in ("; Agency for Cultural Affairs", '; <a class="doc" href="https://www.city.shingu.lg.jp/Info/46" target="_blank" rel="noopener">honorary citizens</a>',
           '; <a class="doc" href="https://www.pref.wakayama.lg.jp/prefg/081300/d00214686.html" target="_blank" rel="noopener">Wakayama on the High Treason case</a>'):
    assert lk in glance, lk
    glance = glance.replace(lk, "", 1)
# the hinge between regions (rail, river border, Kitayama's timber) is a flow: it leaves the dashboard for Theme 4
hinge = re.search(r"\s*<p>It is also a hinge between regions: (.*?)</p>", glance, re.S)
assert hinge, "glance paragraph 4"
glance = glance.replace(hinge.group(0), "")
kita = '; <a class="doc" href="https://www.vill.kitayama.wakayama.jp/kanko/about/" target="_blank" rel="noopener">Kitayama village</a>'
assert kita in glance
glance = glance.replace(kita, "", 1)
HINGE = ('        <p class="kmk-p">Shingū is a hinge between regions: ' + hinge.group(1) + '</p>\n'
         '        <p class="srcline">Sources: <a class="doc" href="https://www.city.shingu.lg.jp/Info/10" target="_blank" rel="noopener">Shingū City profile</a>'
         + kita + '.</p>\n')

# ------------------------------------------------------------------ after: synthesis, resistance, trio, field notes, Kamikura, sources
ac = children(inner(after))
by_id = {attr(c, "id"): c for c in ac if attr(c, "id")}
syn_h2, syn_p, facets, syn_close = ac[0:4]
res_h2, res_ul, res_close, nakagami = ac[4:8]
trio_h1, trio_plan, trio_h2, trio_water = ac[8:12]
assert "Nakagami" in nakagami and attr(res_ul, "class") == "continuity"
fn_study = by_id["fn-study"]
sources = by_id["sources"]
kmk = children(inner(by_id["kamikura-study"]))

# ------------------------------------------------------------------ Kamikura, split into its parts
k_lead, k_intro, k_top, k_chips, k_cards = kmk[0:5]
rest = kmk[5:]
groups, cur = [], None
for c in rest:
    if tagname(c) == "h3":
        cur = [c]; groups.append(cur)
    elif attr(c, "class") == "kmk-dl":
        k_dl = c
    else:
        cur.append(c)
G = {plain(g[0]): g for g in groups}
def grp(key):
    m = [k for k in G if key in k]
    assert len(m) == 1, (key, m)
    return G[m[0]]
g_stop, g_follow, g_lots, g_flow, g_tr, g_sacred, g_gaze = (grp(k) for k in (
    "Where does Kamikura-yama stop?", "What follows the foot?", "The parcel map on the ground", "One flow, several names",
    "Transect:", "Where the landscape itself became sacred", "Who looks at the foot"))
assert len(groups) == 7

# hazard numbers and the hazard card leave Theme 1 for Theme 3 (the plan: hazard polygons “not yet”)
hz_stats = []
for pat in (r'\s*<div><b>83% · 15%</b>.*?</div>', r'\s*<div><b>85%</b><span>inside the maximum assumed river flood.*?</div>'):
    m = re.search(pat, k_top, re.S); assert m, pat
    hz_stats.append(m.group(0).strip()); k_top = k_top.replace(m.group(0), "")
m = re.search(r'\s*<article class="kcard" data-ks="saigai".*?</article>', k_cards, re.S); assert m
saigai_card = m.group(0).strip(); k_cards = k_cards.replace(m.group(0), "")

k_intro = k_intro.replace("This last chapter reads that ground plot by plot", "Theme 1 reads that ground plot by plot")
assert "Theme 1 reads that ground" in k_intro
k_lead = rep1(k_lead, "The main chapters argue that evacuation needs people near high ground", "The chapters above argue that evacuation needs people near high ground")


def with_code(h3, code, pid=None):
    """Put the plan's part code in a Kamikura heading (and an anchor id)."""
    h = h3.replace('<h3 class="trio-head"><b>', '<h3 class="trio-head"%s><b><span class="pcode">%s</span> ' % (f' id="{pid}"' if pid else "", code), 1)
    assert h != h3
    return h


def methods(summary, *blocks):
    return ('        <details class="methods"><summary>%s</summary>\n' % summary
            + "".join("          " + b + "\n" for b in blocks) + "        </details>\n")


ind = lambda b: "        " + b + "\n"

# 1B: the ground — headline, profiles, then the method in a drawer
stop_h3, p_dem, p_four, f_profiles = g_stop
# 1F: alignment
follow = g_follow
# 1E: parcels — registration in a drawer
lots_h3, p_reg, p_two = g_lots
p_two = rep1(p_two, "(−1.7 m to +0.9 m across the seven runs)", "(−1.7 m to +0.9 m across the seven runs of the test below)")
p_reg = rep1(p_reg, "the two other registrations in the runs above. Positions stay approximate; directions are what the test above uses.",
             "the two other registrations in the runs below. Positions stay approximate; directions are what the test below uses.")
# 1C: water — its last paragraph, the channel against the parcel map, is 1E's finding (it needs the registration first)
flow = g_flow
assert flow[-1].startswith('<p class="kmk-p"><b>The channel and the parcel map disagree')
p_chan_parcels, flow = flow[-1], flow[:-1]
# 1G: transect
tr = g_tr
# 5H / 4D / 5I: sacred
sac = g_sacred
p_layers = [c for c in sac if "Layers, not a single origin" in c]; p_living = [c for c in sac if "A living landscape is a remade one" in c]
assert len(p_layers) == 1 and len(p_living) == 1
sac = [c for c in sac if c not in (p_layers[0], p_living[0])]
# 6C / 6D: the finding first, the coding method after it in a drawer (the plan); the album's plate opens 6D
g_h3, g_method, g_fig, g_promo, g_plan, g_plate, g_ours, g_limits = g_gaze
assert ("Four gazes, one frame" in g_method and "The promotional gaze climbs" in g_promo and "The plan adds the backdrop" in g_plan
        and "kmk-plate" in g_plate and "Ours stood at the foot" in g_ours and "What this cannot say" in g_limits)
g_ours = rep1(g_ours, "The channel, the category added to theirs,", "The channel, the category added to Gou &amp; Shibata’s,")

# ------------------------------------------------------------------ the photo sequence of Theme 5 (our photographs, all registered)
SEQ = [("img/field/20250928_120620.jpg", 960, 1280, "A blackboard by the lane: こども食堂, a children’s cafeteria.", "houses and a blackboard"),
       ("img/field/20250928_120624.jpg", 1280, 960, "The lane along the channel, the mountain on the right.", "the lane"),
       ("img/field/20250928_120233.jpg", 1280, 960, "神倉堀端都市下水路, the drainage channel at the foot of Kamikura-yama.", "the channel"),
       ("img/field/20250928_120247.jpg", 1280, 960, "A gourd vine trained over a garden wall beside the channel.", "a garden wall"),
       ("img/field/20250928_115917.jpg", 1280, 960, "Youth Library えんがわ, reached by its own bridge over the channel.", "a bridge to a library"),
       ("img/field/20250928_115930.jpg", 1280, 960, "Youth Library えんがわ, a library in an old house.", "the library"),
       ("img/field/20250928_120149.jpg", 1155, 1280, "妙心寺: its hall beyond a moss garden.", "the temple"),
       ("img/field/20250928_121251.jpg", 1280, 960, "Across the channel from the shrine’s lower precinct: the grounds of the 出雲大社新宮教会.", "a Shinto church across the channel"),
       ("img/field/20250928_115208.jpg", 1280, 960, "The lower torii of 神倉神社 at the foot of the steps.", "the lower torii and the steps"),
       ("img/field/20250928_115712.jpg", 1280, 960, "猿田彦神社 and 神倉三宝荒神社 against the bare rock of the mountain.", "shrines on the rock")]
from PIL import Image
SEQ = [(src, *Image.open(KANSAI + src).size, alt, lab) for src, _w, _h, alt, lab in SEQ]
SEQ_FIG = ('        <figure class="fig seqfig">\n          <ol class="seq">\n'
           + "".join(f'            <li><img src="{src}" alt="{alt}" width="{w}" height="{h}" loading="lazy" decoding="async"><span>{lab}</span></li>\n'
                     for src, w, h, alt, lab in SEQ)
           + '          </ol>\n          <figcaption>At the foot of Kamikura, from the lane to the threshold: the ordinary before the sacred.'
             '<span class="cr">Photos: the authors, field visit, 28 September 2025 · © the authors, all rights reserved</span></figcaption>\n'
           '        </figure>\n')
kokyo = re.search(r'Across the channel two private projects turn old plots into public space: Youth Library えんがわ \(2013\), a library in an old house, and おいしいパーク \(2020–2022\), a vegetable field opened as a park and reading place for it\.', k_cards)
assert kokyo

# ------------------------------------------------------------------ stages (the scrolly, in five places, one map)
def stage_(sid, main, body):
    tag = "main" if main else "div"
    col = mapcol if main else '<div class="mapcol"></div>'
    steps_id = "steps" if main else "steps-" + sid
    return (f'    <{tag} class="stage" id="{"stage" if main else "stage-" + sid}">\n      {col}\n\n'
            f'      <div class="steps" id="{steps_id}">\n{body}      </div>\n    </{tag}>\n')


C = T.chapter
S_PRO = stage_("prologue", True,
               C("P", "Mountain, river, sea", "the convergence that formed the city", "ch-p") + "\n"
               + st("Hinterland · river and sea", "Kii Mountains · relief and forest"))
S_TIME = stage_("time", False,
                C("2C", "The deeper city", "river → railway → reconstruction → road", "ch-2c") + "\n"
                + st("Old town · the natural levee", "Core · seven layers of function", "Castle, Mizunote, Kawaramachi")
                + C("2D", "Railway reorientation", "from the riverfront to the station", "ch-2d") + "\n"
                + st("Rail, road, port", "The urban palimpsest"))
S_HAZ = stage_("hazard", False,
               C("3A", "Kawaramachi and agariya", T.PG("accommodate") + " architecture absorbs the flood", "ch-3a") + "\n"
               + st("Kawaramachi · on the riverbed", "Agariya · redundancy upstream")
               + C("3B", "What followed: works", T.PG("accommodate") + " resistance gathers the residual risk", "ch-3b") + "\n"
               + st("Accommodation to resistance")
               + C("3C", "Four hazard pathways", T.PG("evacuate") + " evacuate · " + T.PG("accommodate") + " accommodate", "ch-3c") + "\n"
               + st("Four directions of risk")
               + C("3D", "The basin flood", "the record that became the design flood", "ch-3d") + "\n"
               + st("Kumano River · risk generated at regional scale", "Climate change · anticipatory hydrology")
               + C("3E", "The city’s own water", "drainage, sluice, pumps", "ch-3e") + "\n"
               + st("Ichida-gawa · risk generated inside the city")
               + C("3F", "Minutes to high ground", T.PG("evacuate") + " evacuate", "ch-3f") + "\n"
               + st("Nankai Trough · minutes to high ground")
               + C("3G", "Exposure, tier by tier", "the full table, collapsed", "ch-3g") + "\n"
               + st("Residents by hazard tier")
               + C("3H", "From the slopes", "sediment and isolation", "ch-3h") + "\n"
               + st("From the slopes · isolation")
               + C("3I", "Coupled hazards", "the pathways meet", "ch-3i") + "\n"
               + st("Beyond the four pathways", "Where the pathways meet")
               + C("3J", "Where a shrinking city can concentrate", T.PG("concentrate") + " concentrate", "ch-3j") + "\n"
               + st("Shingū City · the polycentric hierarchy", "Steering development away from red zones", "Concentrate or evacuate · the plan’s zones"))
S_FLOW = stage_("flows", False,
                C("4B", "Basin and historical flows", "pilgrims, the river and the shrines", "ch-4b") + "\n"
                + st("Sacred geography · Kumano Kodō")
                + C("4C", "The Hongū–Shingū corridor", "a single valley, many flows", "ch-4c") + "\n"
                + st("One river, six functions"))
S_NET = stage_("network", False,
               C("4H", "When the network breaks", T.PG("connect") + " connect", "ch-4h") + "\n"
               + st("Mountain corridors · exposure", "Concentration + connection")
               + C("4I", "Visitors and outsiders", T.PG("evacuate") + " temporary populations", "ch-4i") + "\n"
               + st("The visitor’s Kumano", "Where visitors stand", "Legibility in five languages")
               + C("4", "The watershed scale", T.PG("coordinate") + " coordinate · the final scale-out", "ch-4w") + "\n"
               + st("The downstream fragment", "流域治水 · basin-wide flood management", "Interventions along one system", "Decisions upstream, decades ahead"))
S_EVERY = stage_("everyday", False,
                 C("5I", "Heritage as continuity", "practice, memory and social use", "ch-5i") + "\n"
                 + st("Heritage as memory of river and terrain"))
missing = set(steps) - used
assert not missing, missing

# ------------------------------------------------------------------ assemble
sec = lambda body, label: f'    <section class="after theme" aria-label="{label}">\n{body}    </section>\n\n'
cont = lambda body, label: f'    <section class="after theme-cont" aria-label="{label}">\n{body}    </section>\n\n'
kdiv = lambda body, extra="": f'        <div class="kmk"{extra}>\n{body}        </div>\n'

intro_new = ('    <section class="topsec" id="intro" aria-label="Prologue: Shingū at a glance and the Kumano river system">\n'
             + T.PROLOGUE + glance + "\n      " + ksys_h2 + "\n      " + ksys_p + "\n      " + ksys + "\n    </section>\n\n")

theme1 = sec(T.T1_HEAD
             + '        <div class="kmk" id="kamikura-study">\n'
             + T.part("1A", "the micro-study", "Kamikura–Myōshinji: one physical system", "kamikura")
             + T.T1_LEAD + ind(k_intro) + ind(k_top) + ind(k_chips) + ind(k_cards)
             + ind(with_code(stop_h3, "1B", "t1-1b")) + T.T1_1B + ind(f_profiles)
             + methods("Method · how the foot is found, and how far the elevation model can be trusted", p_dem, p_four)
             + ind(with_code(flow[0], "1C", "t1-1c")) + T.T1_1C + "".join(ind(c) for c in flow[1:])
             + T.T1_1D
             + ind(with_code(lots_h3, "1E", "t1-1e")) + T.T1_1E
             + methods("Method · registering the parcel map", p_reg) + ind(p_two) + ind(p_chan_parcels) + T.T1_1E_TODO
             + ind(with_code(follow[0], "1F", "t1-1f")) + T.T1_1F + "".join(ind(c) for c in follow[1:])
             + ind(with_code(tr[0], "1G", "t1-1g")) + "".join(ind(c) for c in tr[1:]) + T.T1_1G_TODO
             + ind(k_dl)
             + "        </div>\n" + T.T1_CONC, "Theme 1: Ground")

theme2 = (sec(T.T2_HEAD + T.T2_2A + T.T2_2B + T.T2_INTO_STAGE, "Theme 2: Time")
          + S_TIME
          + cont(T.T2_2E + T.part("2F", "ghost morphology", "Nakagami and the vanished town", "t2-2f") + T.T2_2F_LEAD
                 + ind(nakagami) + T.T2_2F_TODO + T.T2_CONC, "Theme 2: Time, continued"))

foot = kdiv(T.T3_FOOT + ind(k_lead)
            + '        <div class="stats kstats">\n          ' + "\n          ".join(hz_stats) + "\n        </div>\n"
            + '        <div class="kcards kcards-one">\n          ' + saigai_card + "\n        </div>\n"
            + T.T3_FOOT_X, ' data-kmk="hazard"')
syn = T.part(None, "centre · hub · edge", "Synthesis · one city, several geographies", "synthesis")
res = T.part(None, "who carries the risk", "From the household to everyone behind the works", "resistance")
theme3 = (sec(T.T3_HEAD, "Theme 3: Hazard")
          + S_HAZ
          + cont(T.T3_I_TODO + T.T3_BOARD, "Theme 3: the plan against the water")
          + "    " + board + "\n\n"
          + cont(T.T3_3K + foot + syn + ind(syn_p) + ind(facets) + ind(syn_close)
                 + res + ind(res_ul) + ind(res_close)
                 + ind(trio_h1) + ind(trio_plan) + ind(trio_h2) + ind(trio_water) + T.T3_CONC, "Theme 3: Hazard, continued"))

theme4 = (sec(T.T4_HEAD + T.T4_4A + HINGE, "Theme 4: Flows")
          + S_FLOW
          + cont(T.T4_4D + kdiv(ind(p_layers[0]), ' data-kmk="network"') + T.T4_4D_TODO
                 + T.T4_FN + ind(fn_study) + T.T4_4G_TODO, "Theme 4: Flows, continued")
          + S_NET
          + cont(T.T4_CONC, "Theme 4: conclusion"))

theme5 = (sec(T.T5_HEAD + T.T5_5A + SEQ_FIG + T.T5_5A_TODO + T.T5_5B + T.T5_5C + T.T5_5D
              + T.T5_5E + '        <p class="kmk-p">' + kokyo.group(0) + "</p>\n" + T.T5_5E_TODO + T.T5_5G
              + kdiv(ind(with_code(sac[0], "5H", "t5-5h")) + "".join(ind(c) for c in sac[1:]), ' data-kmk="sacred"'), "Theme 5: Everyday")
          + S_EVERY
          + cont(kdiv(ind(p_living[0]), ' data-kmk="living"') + T.T5_CONC, "Theme 5: Everyday, continued"))

gz = (ind(with_code(g_h3, "6C", "t6-6c")) + ind(g_fig) + ind(g_promo) + ind(g_plan) + ind(g_ours)
      + methods("Method · how the gazes are coded, and what the coding cannot say", g_method, g_limits)
      + T.T6_6D + ind(g_plate) + T.T6_6D_TODO)
theme6 = sec(T.T6_HEAD + T.T6_6A + T.T6_6B + kdiv(gz, ' data-kmk="gaze"')
             + T.T6_6E + T.T6_6F + T.T6_6G + T.T6_6H + T.T6_CLOSE, "Theme 6: Representation")

srcsec = '    <section class="after theme-cont" id="after" aria-label="Sources and method">\n      ' + sources + "\n    </section>"

new_region = (T.NAV + "\n" + intro_new + "    " + hint + "\n\n" + S_PRO + "\n" + theme1 + theme2 + theme3 + theme4 + theme5 + theme6 + srcsec)
out = head + new_region + tail
open(OUT, "w", encoding="utf-8").write(out)
print("written", OUT, len(out), "bytes; steps", len(used))

# ------------------------------------------------------------------ styles and behaviour for the new layout
CSS = '''
      /* ---------- six themes (kansai/SHINGU.md): heads, parts, drawers, placeholders ---------- */
      .theme-head { max-width: 54rem; margin: 3.6rem 0 1.4rem; padding-top: 1.6rem; border-top: 2px solid var(--accent); }
      .topsec .theme-head { margin-top: 1.4rem; }
      .theme-head .tkick { font-family: "Cormorant Garamond", serif; font-weight: 600; letter-spacing: 0.26em; text-transform: uppercase; color: var(--accent); font-size: 0.92rem; margin: 0 0 0.35rem; }
      .theme-head h2 { font-family: "Cormorant Garamond", "Noto Serif JP", serif; font-weight: 600; font-size: clamp(1.6rem, 3vw, 2.3rem); line-height: 1.2; letter-spacing: 0.01em; margin: 0 0 0.45rem; text-transform: none; }
      .theme-head .tq { font-family: "Cormorant Garamond", serif; font-style: italic; font-size: 1.35rem; color: var(--ink-soft); margin: 0 0 0.5rem; }
      .theme-head .tseq { font-size: 0.84rem; letter-spacing: 0.03em; color: var(--ink-faint); margin: 0 0 0.6rem; }
      .tlead { font-family: "Cormorant Garamond", "Noto Serif JP", serif; font-size: 1.3rem; line-height: 1.5; max-width: 48rem; margin: 0.5rem 0 1rem; color: var(--ink); }
      .tconc { font-family: "Cormorant Garamond", "Noto Serif JP", serif; font-size: 1.38rem; line-height: 1.55; max-width: 50rem; margin: 2.2rem 0 0.6rem; padding: 0.2rem 0 0.2rem 1rem; border-left: 3px solid var(--accent); }
      .pcode { display: inline-block; font: 600 0.72rem/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0.04em; text-transform: none; color: var(--paper); background: var(--accent); border-radius: 2px; padding: 0 0.32rem; margin-right: 0.35rem; vertical-align: 0.12em; }
      .part-tag { margin: 1.6rem 0 0.4rem; font-family: "Cormorant Garamond", serif; letter-spacing: 0.12em; color: var(--ink-soft); }
      .after.theme { padding-bottom: 1rem; }
      .after.theme-cont { padding-top: 1.4rem; padding-bottom: 1.4rem; }
      .todo { max-width: 52rem; margin: 0.8rem 0 1.4rem; padding: 0.65rem 0.95rem 0.3rem; border: 1px dashed #b26a26; border-radius: 3px; background: rgba(251,231,161,0.28); font-size: 0.9rem; line-height: 1.6; }
      .todo .todo-h { margin: 0 0 0.3rem; font-weight: 600; letter-spacing: 0.06em; color: #8a4b12; }
      .todo p { margin: 0 0 0.45rem; }
      details.methods { max-width: 52rem; margin: 0.2rem 0 1.4rem; padding: 0.3rem 0 0.3rem 0.9rem; border-left: 2px solid rgba(87,85,91,0.25); }
      details.methods > summary { cursor: pointer; font-size: 0.9rem; color: var(--ink-soft); letter-spacing: 0.02em; }
      details.methods[open] > summary { margin-bottom: 0.6rem; }
      .xref { max-width: 52rem; font-size: 0.92rem; color: var(--ink-soft); }
      .kx { appearance: none; font: inherit; color: var(--accent); background: none; border: 0; border-bottom: 1px dotted currentColor; padding: 0; cursor: pointer; }
      .kx:hover, .kx:focus-visible { background: #fbe7a1; outline: none; }
      .kcards.kcards-one { grid-template-columns: minmax(0, 40rem); }
      .seqfig { margin: 0.6rem 0 1rem; }
      .seqfig .cr { display: block; font-size: 0.66rem; color: var(--ink-faint); }
      .seq { list-style: none; margin: 0; padding: 0 0 0.4rem; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(150px, 1fr); gap: 0.5rem; overflow-x: auto; }
      .seq li { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; }
      .seq img { width: 100%; height: 150px; object-fit: cover; border-radius: 2px; background: var(--paper-2); }
      .seq span { font-size: 0.78rem; color: var(--ink-soft); line-height: 1.35; }
      .srcline { max-width: 52rem; font-size: 0.76rem; color: var(--ink-faint); line-height: 1.6; }
      .tiers.repr { width: 100%; max-width: 46rem; table-layout: fixed; }
      .tiers.repr th, .tiers.repr td { white-space: normal; overflow-wrap: anywhere; text-align: left; }
'''
def once(s, old, new):
    assert s.count(old) == 1, old[:60]
    return s.replace(old, new)

out = once(out, "    </style>", CSS + "    </style>")
# one map, several stages: it moves into the stage of the step being read
out = once(out, '''          var s = steps[i]; steps.forEach(function (x, j) { x.classList.toggle("is-active", j === i); });''',
           '''          var s = steps[i]; steps.forEach(function (x, j) { x.classList.toggle("is-active", j === i); });
          var stg = s.closest(".stage"), mcol = stg && stg.querySelector(".mapcol"), mwrap = document.getElementById("mapwrap");
          if (mcol && mwrap && mwrap.parentNode !== mcol) { mcol.appendChild(mwrap); measure(); }   // the themes share one map''')
# the Kamikura data load when any of its parts comes near, not only Theme 1
out = once(out, "              io.observe(sec);\n            } else load();\n          }\n          return load;\n        })();\n        function kmkBuild",
           "              io.observe(sec); document.querySelectorAll(\"[data-kmk]\").forEach(function (e) { io.observe(e); });\n            } else load();\n          }\n          return load;\n        })();\n        function kmkBuild")
# a cross-reference button switches the Kamikura map and brings it into view
out = once(out, '''        document.addEventListener("click", function (e) {
          var b = e.target.closest && e.target.closest(".kbase-b"); if (!b) return;''',
           '''        document.addEventListener("click", function (e) {
          var b = e.target.closest && e.target.closest(".kx"), m = document.getElementById("kmkmap"); if (!b || !m) return;
          m.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
        });
        document.addEventListener("click", function (e) {
          var b = e.target.closest && e.target.closest(".kbase-b"); if (!b) return;''')
open(OUT, "w", encoding="utf-8").write(out)
print("patched styles and scripts")
