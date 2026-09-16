#!/usr/bin/env python3
"""
Generates the CSCI 5612 project website.

Run:  python build.py
Then commit the generated .html files and assets/ to your repo.

EDIT REPO_URL BELOW before running.
"""
from pathlib import Path

# ===========================================================================
# EDIT THIS: your public GitHub repository URL (no trailing slash)
# ===========================================================================
REPO_URL = "https://github.com/victormartinez2709/eventRecommender"

OUT = Path(__file__).resolve().parent

TABS = [
    ("index.html", "Introduction"),
    ("dataprep_eda.html", "DataPrep_EDA"),
    ("clustering.html", "Clustering"),
    ("pca.html", "PCA"),
    ("naivebayes.html", "NaiveBayes"),
    ("dectrees.html", "DecTrees"),
    ("svms.html", "SVMs"),
    ("regression.html", "Regression"),
    ("nn.html", "NN"),
    ("conclusions.html", "Conclusions"),
    ("about.html", "About Me"),
]

SITE_TITLE = "Live Electronic Music Discovery in Colorado"
SITE_SUB = "CSCI 5612 &middot; Machine Learning &middot; Project Website &middot; V&iacute;ctor Mart&iacute;nez Gil"


def nav(current: str) -> str:
    links = []
    for href, label in TABS:
        cls = ' class="active"' if href == current else ""
        links.append(f'    <a href="{href}"{cls}>{label}</a>')
    return "\n".join(links)


def page(filename: str, heading: str, lede: str, body: str) -> str:
    title_tab = dict(TABS)[filename]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_tab} &middot; {SITE_TITLE}</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

<header class="site">
  <div class="header-inner">
    <h1 class="site-title">{SITE_TITLE}</h1>
    <p class="site-sub">{SITE_SUB}</p>
  </div>
  <nav class="tabs">
{nav(filename)}
  </nav>
</header>

<main>
<h1>{heading}</h1>
<p class="lede">{lede}</p>
{body}
</main>

<footer class="site">
  <div class="footer-inner">
    CSCI 5612 Project Website &middot; University of Colorado Boulder &middot;
    <a href="{REPO_URL}">Source code and data on GitHub</a>
  </div>
</footer>

</body>
</html>
"""


def model_tab(method_name: str, module_note: str, overview: str = "") -> str:
    """Placeholder tab. Module 1 requires the tab to exist; content comes later."""
    return f"""
<div class="pending">
  <strong>Not yet started.</strong> {module_note}
</div>

<h2>Overview</h2>
<p>To be completed.</p>

<h2>Data</h2>
<p>To be completed.</p>

<h2>Code</h2>
<p>To be completed.</p>

<h2>Results</h2>
<p>To be completed.</p>
"""


# ===========================================================================
# INTRODUCTION
# ===========================================================================

INTRO_BODY = f"""
<p>
Live electronic music occupies an unusual position in the contemporary music economy.
Recorded electronic music circulates almost entirely online, through streaming platforms
and download stores, while the culture that produces it remains stubbornly physical and
local. A record can reach a listener anywhere on earth within seconds of release, but the
performance of that record happens in a specific room, on a specific night, in front of a
few hundred people. Colorado is a substantial market for exactly this kind of event.
Bandsintown, one of the largest live-music platforms, placed Denver among the top ten
United States cities for concert ticket demand in its 2025 year-end report. The state's
venues range from Red Rocks Amphitheatre, which draws international touring acts, down
through mid-sized rooms such as the Ogden Theatre, Cervantes' Masterpiece Ballroom and
the Bluebird Theater, to small clubs like The Black Box and Larimer Lounge that program
electronic music several nights a week. In a representative week in September 2026,
roughly forty events classified as electronic were listed in Denver alone, spread across
nearly twenty distinct venues. The density is high, the turnover is fast, and the
listings change constantly.
</p>

<p>
Finding those shows is considerably harder than the raw numbers suggest. Event
information is scattered across venue calendars, promoter social media accounts,
ticketing platforms, printed flyers and word of mouth, and no single source is complete.
Announcement windows for club events are often short, with a lineup confirmed only two or
three weeks before the date, which means a listener who checks monthly will systematically
miss the smaller shows. Larger touring acts are easy to hear about precisely because they
are marketed heavily, while the long tail of local and regional artists depends on an
audience that already knows to look for them. Genre labels compound the problem rather
than solving it: a single category such as "electronic" is applied to ambient, house,
drum and bass, dubstep and hard techno alike, styles whose audiences overlap far less
than the shared label implies. The result is a discovery failure that runs in both
directions. A listener who would happily pay to see a particular artist may never learn
that the artist performed fifteen minutes from their home. An artist who could have
filled a room plays to a half-empty one because the people who would have come never
heard about it.
</p>

<p>
The consequences fall unevenly, and they fall hardest on the people with the least slack.
For audiences, the cost is a diminished cultural life and money spent on the shows they
happened to hear about rather than the shows they would most have enjoyed. For emerging
artists, the cost is more severe. Live performance is where a large share of working
musicians earn their income, and for electronic artists in particular the live booking is
often the primary source of both revenue and audience growth, since streaming royalties at
small scales are negligible. An artist whose local audience cannot find them is an artist
whose career stalls for reasons that have nothing to do with the quality of their work.
Small and mid-sized venues face the same arithmetic from the other side: they operate on
thin margins, a poorly attended night is a direct loss, and a room that loses money
consistently closes. Promoters, who assume financial risk on each booking, absorb the
volatility in between. The health of a regional music scene therefore depends in a
concrete way on whether the people who would enjoy a given show can actually find out
that it exists.
</p>

<p>
A great deal of effort has gone into solving the analogous problem for recorded music, and
much of it has succeeded. Two decades of work on music recommendation have produced
systems that can suggest a track a listener has never heard and be right often enough to
sustain platforms with hundreds of millions of users. Live music discovery has not kept
pace. The tools that exist largely fall into two categories, and both have the same
limitation. The first alerts a listener when an artist they already follow announces a
nearby date, which is useful but tautological: it can only return what the listener
already knew they wanted. The second filters events by geographic radius and a coarse
genre label, which returns far too much and ranks it by little more than popularity or
proximity. Neither approach can tell a listener that an artist they have never heard of is
playing on Thursday and that they would probably love it. The gap between what is possible
for recorded music and what is available for live music remains wide.
</p>

<p>
What makes this gap interesting is that live music generates a kind of information that
recorded music simply does not have. Every concert bill is a curatorial judgment: a
promoter or booker decides that these particular artists belong on the same stage on the
same night, in a particular order, in a particular room. Those decisions are made by
people with deep knowledge of a local scene, and they encode stylistic affinities far
finer than any genre vocabulary can express. Venues develop identities and programme
consistently within them. Artists tour along routes that reflect where their audiences
actually are. None of this is captured by the audio of a recording or by a listener's play
count, and all of it is publicly visible in the historical record of who performed where
and alongside whom. Whether that accumulated curatorial knowledge can be used to help
people find live music they would love, and specifically whether it can be done for the
Colorado electronic scene where the data is dense and the results can be checked against
lived experience, is the question this project sets out to answer.
</p>

<figure>
  <img src="assets/figures/intro_map.png" alt="Map of Colorado showing the cities and venue clusters in the study region">
  <figcaption>
    <strong>Figure 1. The Colorado study region.</strong> Cities along the Front Range
    corridor, from Fort Collins through Denver to Colorado Springs, together with mountain
    towns that host seasonal electronic events, marking the fifteen locations whose
    listings are traversed by this project.
    Denver is the state&rsquo;s primary live music market, placing in the top ten United
    States cities for concert ticket demand in Bandsintown&rsquo;s 2025 report, with
    Boulder and Colorado Springs within roughly an hour&rsquo;s drive, which
    means a listener's realistic set of options on any given night is regional rather than
    strictly local.
  </figcaption>
</figure>

<h2>Ten Questions This Project Aims to Answer</h2>

<ol class="questions">
  <li>Which artists repeatedly appear on the same bills as one another in Colorado, and do those recurring pairings form identifiable communities within the broader electronic scene?</li>
  <li>Do Colorado venues have distinguishable musical identities, in the sense that the artists booked at one room differ systematically from those booked at another?</li>
  <li>How much of the live electronic activity in Colorado is driven by local and regional artists versus national and international touring acts?</li>
  <li>Does the structure of who performs with whom capture stylistic distinctions finer than the single label "electronic" &mdash; for example, separating house from drum and bass from ambient?</li>
  <li>Is there a seasonal pattern to live electronic events in Colorado, and does it differ between Front Range cities and mountain towns?</li>
  <li>Can the artists whose local following is growing fastest be distinguished from those whose following is flat, using information available before the growth becomes obvious?</li>
  <li>Which venues function as entry points for artists new to the Colorado market, and which tend to host artists who are already established there?</li>
  <li>How far in advance are electronic events announced, and does that lead time differ by venue size or by the prominence of the artist?</li>
  <li>Given the artists a listener already follows, can other artists they are likely to enjoy be identified from live performance history alone, without any audio or listening data?</li>
  <li>Do the events that sell out differ in any observable way from those that do not, beyond the popularity of the headlining artist?</li>
</ol>
"""


# ===========================================================================
# DATAPREP / EDA
# ===========================================================================

FIGURE_SPECS = [
    ("fig01_follower_distribution.png", "Distribution of artist following",
     "Number of Bandsintown followers per artist, on a logarithmic horizontal axis. "
     "The range spans roughly five orders of magnitude, confirming that the sample captures "
     "both small local acts and major touring artists rather than one end of the market."),
    ("fig02_top_artists.png", "The most-followed artists",
     "The twenty artists with the largest followings among those playing Colorado electronic events. "
     "A handful of international names dominate the top of the distribution, which is why a "
     "logarithmic scale is needed for the smaller artists to remain visible at all."),
    ("fig03_upcoming_events.png", "Announced activity per artist",
     "How many upcoming events each artist currently has listed. "
     "A large share of artists have none announced at any given moment, reflecting how short "
     "announcement windows are in this part of the live music market."),
    ("fig04_followers_vs_events.png", "Audience size against announced activity",
     "Each artist plotted by following and by number of upcoming events, both on logarithmic axes. "
     "The relationship is weak, indicating that how busy an artist is cannot be predicted from how "
     "large their audience is: small artists often have more dates listed than large ones."),
    ("fig05_match_method.png", "How each artist was linked to MusicBrainz",
     "Artists split by how their MusicBrainz record was located: an exact identifier supplied by "
     "Bandsintown, a scored name search, or no match at all. "
     "The fuzzy-matched group carries real risk of error, so it is reported separately rather than "
     "folded into a single coverage figure."),
    ("fig06_field_completeness.png", "Field completeness across both sources",
     "The percentage of artists holding a usable value in each field, across both data sources. "
     "Identity and popularity fields are essentially complete, while optional platform links and "
     "MusicBrainz identifiers are sparse, which determined which fields could be relied on."),
    ("fig07_top_genres.png", "Most common genres",
     "The twenty most frequent MusicBrainz genre labels across the collected artists. "
     "Electronic dominates as expected, and the subgenres beneath it (dubstep, house, techno, "
     "deep house, UK garage, melodic techno) reveal the stylistic spread that a single "
     "&ldquo;electronic&rdquo; category conceals."),
    ("fig08_genres_per_artist.png", "Genre labels per artist",
     "How many distinct genre labels each artist carries in MusicBrainz. "
     "Most carry only a handful, so genre alone is a coarse description of any single artist and is "
     "better treated as a weak signal than a definitive label."),
    ("fig09_artist_geography.png", "Where the artists are from",
     "The fifteen most common areas of origin among the collected artists, according to MusicBrainz. "
     "A substantial share are recorded only at country level rather than city level, which limits "
     "how precisely artists can be placed geographically."),
    ("fig10_colorado_precision.png", "Precision of each geographic query",
     "For each MusicBrainz area search, the split between artists genuinely located in Colorado and "
     "results returned in error. "
     "Roughly one result in five names a similarly-titled place in another state, which is why every "
     "row carries an explicit verification flag rather than being trusted as returned."),
]


def eda_figures_html() -> str:
    blocks = []
    for i, (fname, title, caption) in enumerate(FIGURE_SPECS, start=1):
        blocks.append(f"""<figure>
  <img src="assets/figures/{fname}" alt="{title}">
  <figcaption><strong>Figure {i + 1}. {title}.</strong> {caption}</figcaption>
</figure>""")
    return "\n".join(blocks)


EDA_BODY = f"""
<h2>How, Where, and Why the Data Was Gathered</h2>

<p>
This project studies artists performing electronic music in Colorado. Two independent
sources were combined: Bandsintown, a live-music platform, for the artists appearing on
Colorado electronic listings and their audience figures; and MusicBrainz, an open music
encyclopaedia, for genre classification and geographic origin. Neither source alone is
sufficient, and their disagreements are informative in their own right.
</p>

<h2>Source One: Bandsintown</h2>

<p>
Base URL: <code>https://rest.bandsintown.com</code> &middot;
<a href="https://help.artists.bandsintown.com/en/articles/9186477-api-documentation">API documentation</a>
&middot; Authentication: a single <code>app_id</code> query parameter issued through a
Bandsintown for Artists account.
</p>

<div class="table-wrap">
<table>
  <tr><th>Endpoint</th><th>Returns</th><th>Status in this project</th></tr>
  <tr><td><code>GET /artists/{{artistname}}</code></td>
      <td>Artist profile: identifier, name, MusicBrainz id, follower count, upcoming event count, platform links</td>
      <td>Works; the backbone of the dataset</td></tr>
  <tr><td><code>GET /artists/id_{{artist_id}}</code></td>
      <td>The same profile, addressed by numeric identifier</td>
      <td>Works; used for all collection</td></tr>
  <tr><td><code>GET /artists/{{artistname}}/events</code></td>
      <td>Event list with venue, date and full lineup</td>
      <td><strong>Restricted</strong> &mdash; see below</td></tr>
</table>
</div>

<h3>Example GET request</h3>

<pre><code>GET https://rest.bandsintown.com/artists/id_15559410?app_id=APP_ID

Response (abbreviated):
{{
  "id": "15559410",
  "name": "MGNA Crrrta",
  "mbid": "",
  "tracker_count": 8821,
  "upcoming_event_count": 32,
  "image_url": "https://photos.bandsintown.com/large/...jpeg",
  "links": [
    {{ "type": "spotify", "url": "https://open.spotify.com/artist/..." }}
  ]
}}</code></pre>

<h3>A documented limitation of this source</h3>

<div class="note">
  <strong>The events endpoint returns no data for artists other than the key holder.</strong>
  Requests return HTTP 200 with an empty array for every artist tested, including artists
  whose own profile response reports upcoming events. This was verified systematically
  across 24 request variants: three artists with 32, 20 and 6 upcoming events respectively,
  each addressed by name and by numeric identifier, with the date parameter set to
  <code>all</code>, <code>upcoming</code>, <code>past</code>, an explicit range and omitted
  entirely, with and without a trailing slash. Every combination returned an empty list.
  Bandsintown's terms state that an artist key is linked to a single artist unless
  otherwise authorised, which is consistent with this behaviour.
</div>

<p>
The consequence is that this project has no event, venue or performance-lineup data, and
the analysis is therefore at the level of the artist rather than the concert. Access for
research purposes has been requested from the platform.
</p>

<h3>Identifying which artists to collect</h3>

<p>
The API provides no search or enumeration capability: it returns data about an artist
whose identifier is already known, but cannot answer the question "which electronic
artists play in Colorado". Artists were therefore identified from the platform's public
city and genre listing pages, which embed structured schema.org event data including a
link to each performing artist's page:
</p>

<pre><code>https://www.bandsintown.com/c/{{city}}/{{date-range}}/genre/electronic</code></pre>

<p>
Twenty-four Colorado cities were examined across every available date window, from Fort
Collins through the Front Range to Colorado Springs and out to the mountain towns. A
notable finding is that every city and every date range returned an identical set of
artists, indicating that the platform serves a single Denver-region feed for this genre
rather than city-specific listings. The resulting list of 126 artists is therefore close
to the complete public listing surface for electronic music in this market, not a sample
truncated early.
</p>

<h2>Source Two: MusicBrainz</h2>

<p>
Base URL: <code>https://musicbrainz.org/ws/2</code> &middot;
<a href="https://musicbrainz.org/doc/MusicBrainz_API">API documentation</a> &middot;
No authentication required; data is released under open licences. Requests are rate
limited to one per second as the service requires.
</p>

<pre><code>GET https://musicbrainz.org/ws/2/artist/{{mbid}}?inc=tags+genres&amp;fmt=json
GET https://musicbrainz.org/ws/2/artist?query=area:"Colorado"&amp;limit=100&amp;fmt=json</code></pre>

<p>
MusicBrainz supplies what Bandsintown does not: genre classification, artist type,
formation year, and an <code>area</code> field giving geographic origin. It was used two
ways. First, to enrich every artist already collected. Second, and more importantly, to
search directly for artists whose recorded area lies in Colorado &mdash; an independent
sample that does not derive from the first source at all, and which therefore provides a
genuine second view of the same population rather than an annotation of the first.
</p>

<h2>Raw Data</h2>

<p>
Every API response is written to disk exactly as received, before any parsing, as
compressed newline-delimited JSON. Each stored record carries the request URL with
credentials removed, the retrieval timestamp, the HTTP status and the untouched response
body. This makes every table below reproducible from the original bytes, and means a
parsing correction requires re-reading rather than re-collecting. That property was used
in practice during this project: when a loading fault was found, all 126 artist records
were rebuilt from stored responses without a single additional API call.
</p>

<figure>
  <img src="assets/figures/raw_sample.png" alt="Raw JSON as returned by the API">
  <figcaption>
    <strong>Figure 2. Raw data as retrieved.</strong> A single stored artist record showing
    the nested structure returned by the interface, including an empty string where a
    MusicBrainz identifier is absent.
    Empty strings rather than nulls, nested link arrays and string-encoded numbers are all
    visible here, and each is resolved during cleaning.
  </figcaption>
</figure>

<p><a href="{REPO_URL}/tree/main/raw/sample">Link to the raw data</a></p>

<h2>Cleaned Data</h2>

<figure>
  <img src="assets/figures/clean_sample.png" alt="The same data after cleaning">
  <figcaption>
    <strong>Figure 3. The same data after cleaning.</strong> The nested responses have been
    flattened into typed relational tables and joined to MusicBrainz, with the matching
    method retained as a column.
    Every row is now directly usable for analysis, and the provenance of each match remains
    visible rather than being discarded.
  </figcaption>
</figure>

<p><a href="{REPO_URL}/tree/main/data/sample">Link to the cleaned data</a> &mdash;
exported as CSV: artists, follower snapshots, MusicBrainz records, genre tags, and the
Colorado sample.</p>

<h2>Cleaning and Preparation Steps</h2>

<h3>Absent values arrive as empty strings, not nulls</h3>
<p>
Bandsintown returns <code>""</code> rather than <code>null</code> for a missing MusicBrainz
identifier. Because an empty string is not null, it passed through a merge intended to
preserve existing values and would have overwritten valid identifiers with blanks. Empty
strings are now converted to nulls on load, and completeness is measured on that basis.
</p>

<h3>Linking two sources without a shared key</h3>
<p>
Only a minority of artists carry the MusicBrainz identifier that would join the sources
exactly. The remainder are matched by name search, accepting the highest-scoring candidate
only when its score reaches 90. Both the method and the score are stored with every row,
so fuzzy matches can be excluded from any analysis that requires certainty. Figure 6
reports this split rather than presenting a single combined coverage figure, because the
two groups do not carry equal confidence.
</p>

<h3>Geographic queries return other states</h3>
<p>
An unquoted multi-word area search tokenises: <code>area:Fort Collins</code> initially
returned 2,012 results by matching "Collins" anywhere. Quoting the value reduced this to
200. Even quoted, searches return towns of the same name in other states, so each returned
artist is verified against a list of Colorado places and rejected if a competing state is
named, which correctly separates Denver, Colorado from Denver, Pennsylvania. Rejected rows
are retained with a flag rather than deleted, so the filtering is auditable. Figure 11
shows the precision of each query: 80% of results were genuine.
</p>

<h3>Duplicates and repeated collection</h3>
<p>
Artists appear on multiple listing pages and are identified by numeric identifier rather
than by name, so duplicates are removed on insertion. Follower counts are stored as an
append-only series keyed by observation time rather than overwritten, so that repeated
collection accumulates history instead of discarding it.
</p>

<h2>Exploratory Visualizations</h2>

{eda_figures_html()}

<h2>Code</h2>

<p>
All collection, cleaning and figure code is written in Python. The core packages are
<code>requests</code> for retrieval, <code>sqlite3</code> for storage,
<code>beautifulsoup4</code> for parsing structured data out of listing pages, and
<code>matplotlib</code> for figures.
</p>

<ul>
  <li><a href="{REPO_URL}/tree/main/src">All code for this section</a></li>
  <li><a href="{REPO_URL}/blob/main/src/bit_client.py">bit_client.py</a> &mdash; rate-limited API client with raw response capture</li>
  <li><a href="{REPO_URL}/blob/main/src/seed_names.py">seed_names.py</a> &mdash; resolves the artist list against the API</li>
  <li><a href="{REPO_URL}/blob/main/src/crawl.py">crawl.py</a> &mdash; collection loop</li>
  <li><a href="{REPO_URL}/blob/main/src/normalize.py">normalize.py</a> &mdash; converts raw responses into clean tables</li>
  <li><a href="{REPO_URL}/blob/main/src/enrich_musicbrainz.py">enrich_musicbrainz.py</a> &mdash; MusicBrainz enrichment and Colorado search</li>
  <li><a href="{REPO_URL}/blob/main/src/diagnose_events2.py">diagnose_events2.py</a> &mdash; the 24-variant test establishing the events restriction</li>
  <li><a href="{REPO_URL}/blob/main/make_figures.py">make_figures.py</a> &mdash; generates every figure on this page</li>
  <li><a href="{REPO_URL}/blob/main/export_data.py">export_data.py</a> &mdash; exports the CSV files linked above</li>
</ul>
"""


# ===========================================================================
# CONCLUSIONS + ABOUT
# ===========================================================================

CONCLUSIONS_BODY = """
<h2>What This Project Found</h2>

<div class="pending">
  <strong>Status.</strong> Conclusions are written once the analysis is complete, in the
  final project module. This section will contain five or more paragraphs of entirely
  non-technical writing, with supporting images.
</div>

<p>
This section will describe what the project found, in plain language and without reference
to models, methods or technical vocabulary. It is written for a reader with no background
in machine learning or statistics who wants to know what was learned about live electronic
music in Colorado: which parts of the scene connect to which, how venues differ from one
another, whether live performance history really can point a listener toward music they
would enjoy, and what any of it means for the people who play, book and attend these shows.
</p>
"""

ABOUT_BODY = """
<p>
I am V&iacute;ctor Mart&iacute;nez Gil, a master's student in Applied Mathematics at the
University of Colorado Boulder. I was born in Spain and have been based in Colorado while
studying at CU.
</p>

<p>
My academic background is in applied mathematics, with previous research spanning elliptic
eigenvalue problems, mathematical biology and computational neuroscience, and applied
machine learning &mdash; including a National Science Foundation research experience
applying machine learning to social media data, and earlier work building a music
recommendation system on the Million Song Dataset.
</p>

<p>
Outside of coursework I produce and perform electronic music as PETSSS, playing regularly
in the Colorado scene. That is where this project comes from. I have spent enough time on
both sides of the booking process &mdash; as someone playing these rooms and as someone
trying to find out what is happening in them &mdash; to be confident that the discovery
problem described on this site is real, and to be able to tell whether a result the data
produces actually matches how the scene works.
</p>

<p>
This project is also the foundation of my master's thesis, which extends the same data and
the same questions considerably further than the scope of this course.
</p>
"""


# ===========================================================================
# BUILD
# ===========================================================================

PAGES = {
    "index.html": (
        "Introduction",
        "Live electronic music in Colorado, the problem of finding it, and why it matters.",
        INTRO_BODY,
    ),
    "dataprep_eda.html": (
        "Data Preparation and Exploratory Data Analysis",
        "Where the data comes from, how it was gathered and cleaned, and what it looks like.",
        EDA_BODY,
    ),
    "clustering.html": (
        "Clustering",
        "To be completed in Module 2.",
        model_tab("clustering", "This section is completed in Module 2.",),
    ),
    "pca.html": (
        "Principal Component Analysis",
        "To be completed in Module 2.",
        model_tab("principal component analysis", "This section is completed in Module 2.",),
    ),
    "naivebayes.html": (
        "Naive Bayes",
        "To be completed in Module 3.",
        model_tab("Naive Bayes", "This section is completed in Module 3.",),
    ),
    "dectrees.html": (
        "Decision Trees",
        "To be completed in Module 3.",
        model_tab("decision trees", "This section is completed in Module 3.",),
    ),
    "svms.html": (
        "Support Vector Machines",
        "To be completed in Module 4.",
        model_tab("support vector machines", "This section is completed in Module 4.",),
    ),
    "regression.html": (
        "Regression",
        "To be completed in Module 5.",
        model_tab("regression", "This section is completed in Module 5.",),
    ),
    "nn.html": (
        "Neural Networks",
        "To be completed in Module 5.",
        model_tab("neural networks", "This section is completed in Module 5.",),
    ),
    "conclusions.html": (
        "Conclusions",
        "To be completed in the final module.",
        CONCLUSIONS_BODY,
    ),
    "about.html": (
        "About Me",
        "Background, and where this project comes from.",
        ABOUT_BODY,
    ),
}


def main() -> None:
    if "YOUR-USERNAME" in REPO_URL:
        print("!! REPO_URL is still a placeholder. Edit it at the top of build.py.\n")

    for filename, (heading, lede, body) in PAGES.items():
        (OUT / filename).write_text(page(filename, heading, lede, body), encoding="utf-8")
        print(f"  wrote {filename}")

    print(f"\n{len(PAGES)} pages written to {OUT}")


if __name__ == "__main__":
    main()
