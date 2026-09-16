# eventRecommender

CSCI 5612 project — live electronic music events in Colorado.

**Website:** https://victormartinez2709.github.io/eventRecommender/

This repository holds the data collection pipeline and the project website.

## What the code does

Bandsintown's API has no search and no genre filter: it can return data about an
artist whose identifier is already known, but it cannot answer "which electronic
artists play in Colorado". The pipeline therefore runs in two stages — discover
artists from the public city and genre listing pages, then collect structured data
about each one through the API.

```
src/config.py       settings, paths, Colorado city list  (edit this, not the scripts)
src/db.py           creates the SQLite database
src/bit_client.py   Bandsintown API client — rate limiting, retries, raw capture
src/seeds.py        stage 1: discover Colorado electronic artists from listing pages
src/crawl.py        stage 2: collect artist profiles and full event histories
src/normalize.py    turn the raw API responses into clean tables
```

## Storage

```
raw/      every API response exactly as received, gzipped, never edited
data/     the SQLite database
assets/   website stylesheet and figures
```

Raw responses are kept immutable so that a parsing correction means re-reading the
stored files rather than re-collecting from the API.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env     # then paste your Bandsintown app_id into .env
```

`.env` is gitignored and never committed. API keys are stripped from stored
responses before they are written to `raw/`.

## Running it

```bash
python src/db.py                      # once, creates the database
python src/bit_client.py PETSSS       # smoke test: one real API call

python src/seeds.py --range this-week # discover artists
python src/crawl.py --limit 20        # collect, small test first
python src/crawl.py                   # collect, full run

python src/normalize.py               # clean into tables
python make_figures.py                # regenerate the website figures
python build.py                       # regenerate the website HTML
```

## Data source

Bandsintown REST API — `https://rest.bandsintown.com`
[API documentation](https://help.artists.bandsintown.com/en/articles/9186477-api-documentation)

Collection is rate limited to one request per second. Data is used for
non-commercial academic coursework.
