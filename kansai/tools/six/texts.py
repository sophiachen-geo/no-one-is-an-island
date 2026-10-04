"""New text for the six-theme layout: theme heads, part heads, conclusions, cross-references and the visible
placeholders (.todo) for evidence the plan calls for but the page does not hold yet. Wording follows kansai/SHINGU.md."""


def head(tid, kick, title, q, seq, lead=None):
    h = f'''      <header class="theme-head" id="{tid}">
        <p class="tkick">{kick}</p>
        <h2 id="{tid}-h">{title}</h2>
        <p class="tq">{q}</p>
        <p class="tseq">{seq}</p>
'''
    if lead:
        h += f'        <p class="tlead">{lead}</p>\n'
    return h + "      </header>\n"


def part(code, kick, title, pid=None):
    i = f' id="{pid}"' if pid else ""
    c = f'<span class="pcode">{code}</span> ' if code else ""
    return f'        <h3 class="trio-head"{i}><b>{c}{kick}</b>{title}</h3>\n'


def lead(t):
    return f'        <p class="tlead">{t}</p>\n'


def conc(t):
    return f'        <p class="tconc">{t}</p>\n'


def todo(code, *paras):
    body = "".join(f"          <p>{p}</p>\n" for p in paras)
    return f'''        <aside class="todo" data-plan="{code}">
          <p class="todo-h">To add · {code}</p>
{body}        </aside>
'''


def chapter(code, title, tags, cid=None):
    i = f' id="{cid}"' if cid else ""
    return f'        <div class="chapter"{i}><p class="cn">{code}</p><h2>{title}</h2><div class="tags">{tags}</div></div>\n'


PG = lambda k: f'<svg class="pg"><use href="#pg-{k}"/></svg>'

PROLOGUE = '''      <header class="theme-head" id="prologue">
        <p class="tkick">Prologue</p>
        <h2 id="prologue-h">Why Shingū, why here?</h2>
        <p class="tlead">A shrinking city remains a disproportionately important regional node because of the geography that formed it.</p>
        <p class="tseq">regional node + shrinking population + mountain, river and sea</p>
      </header>
'''

T1_HEAD = head("t1", "Theme 1 · Ground", "Landform, water and the physical structure of the city", "What structures space?",
               "terrain → water → bridges → parcels → section")
T1_LEAD = lead("This is not “a shrine neighbourhood.” It is one physical system: mountain edge + drainage + parcels + houses + institutions.")
T1_1B = lead("Kamikura-yama does not gradually dissolve into town. It terminates in a measurable topographic threshold: 40° above the foot, 1° below it.")
T1_1C = lead("Water is channelled through the exact zone where mountain and urban plain meet.")
T1_1D = (part("1D", "流れ · crossings", "Bridge census: where access crosses the water", "t1-1d")
         + lead("What happens when a shared hydraulic corridor cuts across everyday access?")
         + todo("1D",
                "Show the channel continuously and mark every crossing of 神倉堀端都市下水路, classified by function: private dwelling access, shared or residential access, pedestrian access, institutional access, road crossing. Photograph representative types.",
                "Start from <code>kansai/field/bridges.csv</code> (the crossings OpenStreetMap maps) and add the footbridges to private houses on site, as the field kit describes (<code>kansai/field/README.md</code>). Theme 1 owns the census and its geometry; Theme 5 returns to it with photographs only."))
T1_1E = lead("Property structure records a spatial order that is not identical to either terrain or present-day drainage infrastructure.")
T1_1E_TODO = todo("1E",
                  "Parcel size, depth, frontage and orientation as an analytical figure, and for each parcel whether it runs perpendicular or parallel to the slope, fronts the water, bridges it or is bisected by later infrastructure.")
T1_1F = lead("Are these apparent alignments statistically distinguishable from nearby urban fabric?")
T1_1G_TODO = todo("1G",
                  "Make the transect one of the largest visuals on the page and annotate, at this stage only, relief, slope, runoff, the channel, the parcel and building fabric and the school. Themes 3 and 5 reuse the same section and add risk, then meaning.")
T1_CONC = conc("The ground does not merely underlie Shingū. It establishes spatial constraints to which water, streets, parcels and buildings respond differently.")

T2_HEAD = head("t2", "Theme 2 · Time", "Persistence, transformation and morphological time", "What survives change?",
               "aerials → inherited alignments → railway → reconstruction → ghost morphology",
               "Which of the structures of Theme 1 persist when individual objects disappear? Here history becomes change detection.")
T2_2A = (part("2A", "change detection", "The historical aerial series", "t2-2a")
         + todo("2A",
                "Historical aerial photographs of the same extent, crop and orientation: early, post-war reconstruction, later twentieth century, present. Track buildings, roads, the forest edge, the channel, the large institutional plots and, where possible, the parcels.",
                "Annotate what survives: a house disappears and its parcel persists; a road widens and keeps its alignment; a building changes and the sacred threshold persists; the forest edge moves; the channel becomes engineered. GSI’s 地図・空中写真閲覧サービス is the place to start."))
T2_2B = (part("2B", "object and form", "Material age against morphological age", "t2-2b")
         + lead("Object age is not morphology age.")
         + todo("2B",
                "Small before-and-after pairs from the field photographs and the aerials: an old parcel with a new house, an old route with a reconstructed street, an old sacred access with new paving, an old water corridor in a modern concrete channel."))
T2_INTO_STAGE = '        <p class="xref">On the map below: the river city, the railway city and their layers. The channel’s own chronology sits with the water, in <a href="#t1-1c">Theme 1</a>.</p>\n'
T2_2CD_TODO = todo("2C–2D",
                   "Recast the steps above as four spatial regimes, river city, railway city, reconstruction city and road city, rather than a sequence of events.",
                   "A before-and-after plan of the railway: which way the city faced before it, and which axes mattered after it, the riverfront against the station.")
T2_2E = (part("2E", "rupture", "Disaster and reconstruction", "t2-2e")
         + '        <p class="xref">Here disaster matters only as a rupture in time: what physically changed afterwards. Its mechanisms belong to <a href="#t3">Theme 3</a>, where the fire that followed the last Nankai earthquake is listed among the slower pressures.</p>\n'
         + todo("2E",
                "Demolished fabric, reconstruction blocks, changed road widths and building materials, parcels that persisted or were amalgamated, after the fire and after the floods."))
T2_2F_LEAD = lead("Can an urban form remain culturally legible after it has physically vanished?")
T2_2F_TODO = todo("2F",
                  "Former lanes, lost neighbourhood structures, demolished buildings, literary memory, historic photography and present-day absence, in text only: the page does not locate the district, and Theme 6 returns to Nakagami as representation.")
T2_CONC = conc("Shingū contains several cities at once. Material replacement is often faster than the replacement of routes, boundaries, orientations and remembered spatial relations.")

T3_HEAD = head("t3", "Theme 3 · Hazard", "Hazard as a producer of urban form", "How does disturbance produce form?",
               "Kawaraya → four hazards → infrastructure → evacuation → compact planning",
               "The contradiction, before the evidence: the location plan concentrates a shrinking town where the water goes, and leaves evacuation to close the gap (<a href=\"#t3-3j\">3J</a>).")
T3_BOARD = part("3J", "the plan against the water", "Finding, strategy, test", "t3-3j")
T3_FOOT = (part("3L", "at the foot of the high ground", "The refuge inside the hazard", "t3-foot"))
T3_FOOT_X = ('        <p class="xref"><button type="button" class="kh kx" data-ks="saigai">Show the hazards on the Kamikura map</button>, the ground of <a href="#t1">Theme 1</a> read now as risk.</p>\n'
             + todo("3L",
                    "The mountain-to-city transect of Theme 1, second appearance: add runoff and debris movement down the section, evacuation up it, the refuge, and the flood and tsunami extents where they reach."))
T3_3K = ('        <p class="part-tag"><span class="pcode">3K</span> Youth Library えんがわ · おいしいパーク</p>\n'
         '        <p class="xref">At the foot of Kamikura, a library in an old house and a field opened as a park show adaptation of another kind: reuse and incremental change rather than defence against hazard. Their home is <a href="#t5-5e">Theme 5</a>.</p>\n')
T3_I_TODO = todo("3I",
                 "Redraw the coupling matrix as a network: earthquake and levee condition, river and urban drainage, sediment and channel capacity, slope failure and road access, tsunami and drainage recovery, dams and sediment. Keep the matrix beneath it as the evidence.")
T3_CONC = conc("Hazard is not something occasionally superimposed on Shingū. It repeatedly changes its architecture, infrastructure, settlement choices, movement systems and reconstruction.")

T4_HEAD = head("t4", "Theme 4 · Flows", "Movement and networks", "What makes the city operate?",
               "pilgrimage → river and road → a temple’s network → bicycle → network vulnerability → visitors → the watershed",
               "So far the city has been read as geometry. Now the same city is read as movement.")
T4_4A = (part("4A", "the framework", "The three structures and the two lenses", "t4-4a")
         + '        <p class="kmk-p">This page reads urban form in three structures: the ground (下部構造), the lots (中部構造), and the buildings and open spaces on them (上部構造). Read only as structures, the city stands still. Shingū needs two more lenses: flows (流れ), which this theme follows, and representation (まなざし), which <a href="#t6">Theme 6</a> takes up.</p>\n')
T4_4B_TODO = todo("4B",
                   "One basin map of successive and overlapping flows with the hazards stripped away: water, timber, pilgrims, goods, river transport, railway, roads, tourism. The prologue’s map of timber and sea lanes and the pilgrim map above are its first layers.")
T4_4D = (part("4D", "a temple in a network", "Myōshinji as a network node", "t4-4d")
         + lead("Physical size and network importance are not the same thing."))
T4_4D_TODO = todo("4D",
                  "Map the reach the paragraph above describes: Myōshinji’s small footprint against the provinces its collections came from, its religious affiliation, and the movement of money, people, material and ritual that tied the foot of Kamikura to the Kumano shrines and beyond.")
T4_FN = (part("4E", "4E–4G · the moving body", "Field notes · Shingū’s three shrines by bicycle", "fieldnotes")
         + lead("The morphology of Shingū changes depending on the moving body used to measure it."))
T4_4G_TODO = todo("4G",
                  "Photograph route sequences: an ordinary lane, the channel, a house edge, the temple threshold, the steps, the mountain, narrated as continuous movement rather than as landmarks. The first sequence is in <a href=\"#t5\">Theme 5</a>.")
T4_CONC = conc("Shingū is not simply a collection of fixed sites. It is a junction through which water, people, goods, information and risk continually move.")

T5_HEAD = head("t5", "Theme 5 · Everyday", "Sacred landscape, everyday life and contemporary continuity", "How are these systems actually inhabited?",
               "houses → temple → bridges → parcels → library and park → school → sacred and ordinary",
               "After the modelling, back to the street.")
T5_5A = (part("5A", "ordinary → sacred", "Up the lane to the threshold", "t5-5a")
         + lead("The sacred landscape emerges gradually, from the ordinary."))
T5_5A_TODO = todo("5A",
                  "The sequence still lacks the school, a bicycle and Gotobiki-iwa itself; add them when the next walk photographs the whole foot.")
T5_5B = (part("5B", "a temple as a neighbour", "Myōshinji, second appearance", "t5-5b")
         + '        <p class="xref"><a href="#t4-4d">Theme 4</a> placed 妙心寺 in its network; here it is a neighbour: a hall behind a moss garden, its board by the lane. <button type="button" class="kh kx" data-ks="keidai">Show the precincts on the Kamikura map</button>.</p>\n'
         + todo("5B", "Its actual footprint, the houses beside it, its relation to the street and its local access, mapped at the scale of the plot."))
T5_5C = (part("5C", "a threshold to home", "Bridges, second appearance", "t5-5c")
         + lead("A piece of municipal drainage infrastructure is also somebody’s threshold to home.")
         + todo("5C", "Three or four photographs from the census of <a href=\"#t1-1d\">Theme 1</a>: a front door across the channel, a garden access, a shared bridge, an institutional bridge. No statistics here."))
T5_5D = (part("5D", "interlocking ground", "Parcels, second appearance", "t5-5d")
         + lead("Sacred, public and domestic territories physically interlock rather than form separate districts.")
         + '        <p class="xref"><button type="button" class="kh kx" data-ks="yashiki">Show the plots on the Kamikura map</button>: the shrine’s lower precinct, the temple row, the school compound and the houses share a single grid.</p>\n')
T5_5E = (part("5E", "5E–5F · reuse", "Youth Library えんがわ and おいしいパーク", "t5-5e")
         + lead("Continuity does not require freezing the old building in its old function."))
T5_5E_TODO = todo("5E–5F",
                  "Who uses the library and the park, the threshold between inside and outside, what stood on the park’s ground before, and how both sit against the lane, the channel and the mountain, mapped at their own small scale.")
T5_5G = (part("5G", "the school, every day", "Kamikura Elementary School", "t5-5g")
         + lead("The places used during extraordinary moments are often maintained through completely ordinary daily use.")
         + '        <p class="xref"><a href="#t3-foot">Theme 3</a> read the school and its gym as refuges inside the hazard. Here it is children, education and a neighbourhood centre: the same site at another time.</p>\n'
         + todo("5G", "The school day at the foot: the compound, its gate to the lane, its users, photographed and described."))
T5_CONC = conc("What appears on a hazard map as infrastructure and on a heritage map as sacred space is, on the ground, also someone’s route to school, front door, garden, library or meeting place.")

T6_HEAD = head("t6", "Theme 6 · Representation", "Visibility and the Kumano gaze", "Why have we not usually seen the city this way?",
               "GIS and drawings → photography → literature → tourist map → the Kumano gaze",
               "Not new geography: a re-reading of what the page has already shown.")
T6_6A = (part("6A", "the fifth layer", "A single place, many Shingūs", "t6-6a")
         + lead("Are these maps describing the same place? Technically yes; epistemically, not really. Each selects a different Shingū.")
         + todo("6A", "The same ground at the foot of Kamikura shown several ways side by side: the elevation model, the cadastral map, the hazard map, a tourist map, a photograph."))
T6_6B = (part("6B", "what a drawing can hold", "Plan, section, route, network", "t6-6b")
         + '''        <figure class="fig">
          <table class="tiers repr">
            <thead><tr><th scope="col">Representation</th><th scope="col">Makes visible</th><th scope="col">Tends to hide</th></tr></thead>
            <tbody>
              <tr><th scope="row">Plan</th><td>adjacency</td><td>verticality</td></tr>
              <tr><th scope="row">Section</th><td>vertical relation</td><td>network reach</td></tr>
              <tr><th scope="row">Route</th><td>sequence</td><td>simultaneous spatial context</td></tr>
              <tr><th scope="row">Network</th><td>connectivity</td><td>material experience</td></tr>
              <tr><th scope="row">Hazard GIS</th><td>exposure</td><td>cultural meaning</td></tr>
              <tr><th scope="row">Cadastral map</th><td>property order</td><td>lived movement</td></tr>
              <tr><th scope="row">Photograph</th><td>experience and materiality</td><td>invisible systems</td></tr>
            </tbody>
          </table>
          <div class="cap">Every drawing on this page belongs to a kind in this table; none of them is sufficient by itself.</div>
        </figure>
''')
T6_6D = '        <p class="part-tag"><span class="pcode">6D</span> Kubo Photo Studio · 『熊野百景写真帖』</p>\n'
T6_6D_TODO = todo("6D", "How did these plates help produce Kumano as a coherent visual region? The motifs that recur across the album (mountains, shrines, pilgrimage, water, picturesque views) against today’s tourism imagery.")
T6_6E = (part("6E", "literature", "Nakagami, second appearance", "t6-6e")
         + lead("How representation keeps a vanished landscape perceptible.")
         + '        <p class="xref"><a href="#t2-2f">Theme 2</a> read Nakagami Kenji’s 路地 as ghost morphology. Literature does something an elevation model cannot.</p>\n'
         + todo("6E", "Text only, as in Theme 2: what the novels keep perceptible, without locating the district."))
T6_6F = (part("6F", "mapping as evidence", "The tourist map", "t6-6f")
         + todo("6F", "Read the tourist maps literally: what is labelled, omitted, connected or isolated; what becomes a destination and what disappears between destinations. If the drainage corridor, the school and the ordinary neighbourhood vanish while the shrine and the mountain dominate, say so. Link the maps; do not reproduce them."))
T6_6G = (part("6G", "the culmination", "The therapeutic Kumano gaze", "t6-6g")
         + '        <p class="kmk-p">Forest, sacred, ancient, healing, pilgrimage, purification; and concrete drains, schools, maintenance, roads, pumps, housing, ageing infrastructure, industry, hazard management.</p>\n'
         + lead("Both are real, but one has become much more representationally dominant. This page restores the other.")
         + todo("6G", "The argument in full, built from the evidence of Themes 1–5 and the coded gazes above."))
T6_6H = (part("6H", "constructions", "Then, now, promoted, measured", "t6-6h")
         + todo("6H", "A controlled comparison of the same landscape: the 1913 plate, a promotional image (linked, not reproduced), our photograph and the map."))
T6_CLOSE = '''        <p class="closing">GIS showed one system. The cadastral map showed another. The elevation model showed another. Historical aerials show persistence. Network analysis showed movement. Field cycling showed lived permeability. Photographs showed what official imagery overlooks.</p>
''' + conc("Shingū changes depending on whether it is viewed as terrain, heritage, hazard, infrastructure, network or home. None is sufficient by itself.")

NAV = '''    <nav class="toc" id="contents" aria-label="Contents">
      <p class="toc-h">Contents</p>
      <div class="toc-cols">
        <ul class="toc-g">
          <li><a href="#prologue">Prologue · Why Shingū, why here?</a></li>
          <li><a href="#intro">Shingū at a glance</a></li>
          <li><a href="#kumano-system">The Kumano as one system</a></li>
        </ul>
        <ol class="toc-g toc-ch">
          <li><a href="#t1">Ground · what structures space?</a></li>
          <li><a href="#t2">Time · what survives change?</a></li>
          <li><a href="#t3">Hazard · how does disturbance produce form?</a></li>
          <li><a href="#t4">Flows · what makes the city operate?</a></li>
          <li><a href="#t5">Everyday · how are these systems inhabited?</a></li>
          <li><a href="#t6">Representation · why have we not seen the city this way?</a></li>
        </ol>
        <ul class="toc-g">
          <li><a href="#kamikura">The Kamikura micro-study</a></li>
          <li><a href="#fieldnotes">Field notes · Shingū’s three shrines by bicycle</a></li>
          <li><a href="#sources">Sources &amp; method</a></li>
        </ul>
      </div>
    </nav>
'''
