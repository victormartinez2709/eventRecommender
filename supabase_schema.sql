-- ===========================================================================
-- Supabase / Postgres schema for the Colorado live music dataset.
--
-- Paste this whole file into the Supabase SQL Editor and run it once.
-- Safe to re-run: every statement is IF NOT EXISTS or CREATE OR REPLACE.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Venues
-- ---------------------------------------------------------------------------
create table if not exists venues (
    venue_id      text primary key,
    name          text,
    city          text,
    state_code    text,
    country_code  text,
    address       text,
    postal_code   text,
    latitude      double precision,
    longitude     double precision,
    timezone      text,
    market        text,
    dma_id        text,
    url           text,
    updated_at    timestamptz not null default now()
);
create index if not exists idx_venues_city on venues (city, state_code);

-- ---------------------------------------------------------------------------
-- Artists (Ticketmaster calls them attractions)
-- ---------------------------------------------------------------------------
create table if not exists attractions (
    attraction_id   text primary key,
    name            text not null,
    url             text,
    segment_id      text,
    segment_name    text,
    genre_id        text,
    genre_name      text,
    subgenre_id     text,
    subgenre_name   text,
    upcoming_events integer,
    image_url       text,
    first_seen_at   timestamptz,
    updated_at      timestamptz not null default now()
);
create index if not exists idx_attractions_genre on attractions (genre_name, subgenre_name);
create index if not exists idx_attractions_name on attractions (lower(name));

create table if not exists attraction_links (
    attraction_id text not null references attractions (attraction_id) on delete cascade,
    platform      text not null,
    url           text not null,
    primary key (attraction_id, platform, url)
);

-- ---------------------------------------------------------------------------
-- Events: current state, upserted on every weekly run
-- ---------------------------------------------------------------------------
create table if not exists events (
    event_id        text primary key,
    name            text,
    url             text,
    venue_id        text references venues (venue_id),

    local_date      date,
    local_time      time,
    datetime_utc    timestamptz,
    timezone        text,
    status          text,

    onsale_start    timestamptz,
    onsale_end      timestamptz,

    price_min       numeric(10, 2),
    price_max       numeric(10, 2),
    price_currency  text,

    promoter_name   text,

    segment_id      text,
    segment_name    text,
    genre_id        text,
    genre_name      text,
    subgenre_id     text,
    subgenre_name   text,

    -- cleaning output, carried alongside so one table answers most questions
    genre_clean     text,
    subgenre_clean  text,
    is_electronic   boolean not null default false,
    is_duplicate    boolean not null default false,
    is_cancelled    boolean not null default false,
    dedup_group     text,
    venue_canonical_id text,
    headliner       text,
    lineup_size     integer not null default 0,
    lead_time_days  integer,
    weekday         smallint,

    first_seen_at   timestamptz,
    last_seen_at    timestamptz,
    updated_at      timestamptz not null default now()
);
-- For a database created before these columns existed: create table if not
-- exists would silently skip them, so add them explicitly.
alter table events add column if not exists venue_canonical_id text;
alter table events add column if not exists headliner text;

create index if not exists idx_events_date     on events (local_date);
create index if not exists idx_events_cvenue   on events (venue_canonical_id);
create index if not exists idx_events_genre    on events (genre_clean, subgenre_clean);
create index if not exists idx_events_venue    on events (venue_id);
create index if not exists idx_events_electro  on events (is_electronic) where is_electronic;
create index if not exists idx_events_usable   on events (local_date)
    where not is_duplicate and not is_cancelled;

-- ---------------------------------------------------------------------------
-- Lineups: two artists sharing an event_id is a co-performance edge
-- ---------------------------------------------------------------------------
create table if not exists event_attractions (
    event_id      text not null references events (event_id) on delete cascade,
    attraction_id text not null references attractions (attraction_id) on delete cascade,
    position      integer,
    primary key (event_id, attraction_id)
);
create index if not exists idx_ea_attraction on event_attractions (attraction_id);

-- ---------------------------------------------------------------------------
-- THE IMPORTANT ONE. Append-only.
--
-- Ticketmaster is a live ticketing feed, not an archive: events disappear once
-- they go off-sale, and price and status change while they are listed. This
-- table is the only record of what an event looked like at a point in time,
-- and it cannot be backfilled -- it exists only for weeks you actually ran the
-- collection.
-- ---------------------------------------------------------------------------
create table if not exists event_observations (
    event_id     text not null,
    observed_at  timestamptz not null,
    status       text,
    price_min    numeric(10, 2),
    price_max    numeric(10, 2),
    lineup_size  integer,
    days_until   integer,
    primary key (event_id, observed_at)
);
create index if not exists idx_obs_event on event_observations (event_id);
create index if not exists idx_obs_time  on event_observations (observed_at);

-- ---------------------------------------------------------------------------
-- The Ticketmaster classification taxonomy
-- ---------------------------------------------------------------------------
create table if not exists classifications (
    segment_id    text not null,
    segment_name  text,
    genre_id      text not null default '',
    genre_name    text,
    subgenre_id   text not null default '',
    subgenre_name text,
    primary key (segment_id, genre_id, subgenre_id)
);

-- ---------------------------------------------------------------------------
-- One row per weekly collection run
-- ---------------------------------------------------------------------------
create table if not exists runs (
    run_id       text primary key,
    started_at   timestamptz not null,
    finished_at  timestamptz,
    api_calls    integer,
    cache_hits   integer,
    events_seen  integer,
    events_new   integer,
    synced_rows  integer,
    notes        text
);

-- ===========================================================================
-- Views: what the models will actually read
--
-- These are dropped first rather than replaced. CREATE OR REPLACE VIEW can only
-- append columns to the end of a view's output, and "select e.*" shifts every
-- column along whenever the events table gains one -- which Postgres reports as
-- an attempt to rename a column. A view stores nothing, so recreating is free.
-- v_events_electronic is dropped before v_events_usable because it reads it.
-- ===========================================================================

drop view if exists v_events_electronic;
drop view if exists v_events_usable;
drop view if exists v_event_history;
drop view if exists v_venue_genre_mix;


-- Every usable event, duplicates and cancellations removed.
create or replace view v_events_usable as
select e.*,
       v.name  as venue_name,
       v.city  as venue_city,
       v.latitude,
       v.longitude
from events e
left join venues v using (venue_id)
where not e.is_duplicate
  and not e.is_cancelled;

-- Electronic events only, upcoming first.
create or replace view v_events_electronic as
select * from v_events_usable
where is_electronic
order by local_date;

-- How each event changed across observations: price movement and sell-outs.
create or replace view v_event_history as
select event_id,
       count(*)                                as observations,
       min(observed_at)                        as first_observed,
       max(observed_at)                        as last_observed,
       min(price_min)                          as lowest_price_seen,
       max(price_max)                          as highest_price_seen,
       count(distinct status)                  as status_changes,
       bool_or(status ilike '%offsale%')       as went_offsale
from event_observations
group by event_id;

-- Genre mix per venue: the basis for clustering venues by what they programme.
create or replace view v_venue_genre_mix as
select coalesce(e.venue_canonical_id, v.venue_id) as venue_id,
       v.name as venue_name,
       v.city,
       e.genre_clean,
       count(*) as events
from events e
join venues v using (venue_id)
where not e.is_duplicate and not e.is_cancelled and e.genre_clean is not null
group by coalesce(e.venue_canonical_id, v.venue_id), v.name, v.city, e.genre_clean;
