-- Steam personal library and play-cost analysis: core schema (v1.0)
--
-- Target: openGauss 7.0.0-RC3 (PostgreSQL-compatible dialect).
-- All objects live in the dedicated schema "steam" so the application
-- account never needs privileges on the shared public schema.
--
-- Run as the business account (steam_app) after selecting the steam_library
-- database. The script is idempotent for a clean database: it creates the
-- schema if absent and uses IF NOT EXISTS / DO blocks for the objects.
--
-- Re-running this file on a database that already holds data does NOT drop
-- or truncate anything. Schema migrations are handled separately later.

CREATE SCHEMA IF NOT EXISTS steam AUTHORIZATION steam_app;
SET search_path TO steam, public;

-- ---------------------------------------------------------------------------
-- 1. games: one row per distinct game (Steam-synced or manually added)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS steam.games (
    game_id          BIGSERIAL     PRIMARY KEY,
    steam_appid      BIGINT        UNIQUE,           -- NULL for manual games
    game_name        VARCHAR(255)  NOT NULL,
    developer        VARCHAR(255),
    image_url        TEXT,
    is_free_to_play  BOOLEAN,                        -- NULL = store classification unknown
    source           VARCHAR(16)   NOT NULL DEFAULT 'manual'
                     CHECK (source IN ('steam', 'manual')),
    created_at       TIMESTAMP     NOT NULL DEFAULT now(),
    updated_at       TIMESTAMP     NOT NULL DEFAULT now()
);

COMMENT ON TABLE  steam.games IS 'Game catalogue; steam_appid is the sync dedupe key';
COMMENT ON COLUMN steam.games.is_free_to_play IS 'Store F2P flag, NOT the users acquisition type';
COMMENT ON COLUMN steam.games.source IS 'steam = synced from API, manual = entered by user';

-- ---------------------------------------------------------------------------
-- 2. genres: bilingual genre dictionary
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS steam.genres (
    genre_id        BIGSERIAL    PRIMARY KEY,
    steam_genre_id  VARCHAR(32)  UNIQUE,
    name_zh         VARCHAR(64)  NOT NULL,
    name_en         VARCHAR(64)  NOT NULL
);

COMMENT ON TABLE steam.genres IS 'Genre dictionary with both display languages';

-- ---------------------------------------------------------------------------
-- 3. game_genres: many-to-many between games and genres
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS steam.game_genres (
    game_id   BIGINT NOT NULL REFERENCES steam.games(game_id)  ON DELETE CASCADE,
    genre_id  BIGINT NOT NULL REFERENCES steam.genres(genre_id) ON DELETE RESTRICT,
    PRIMARY KEY (game_id, genre_id)
);

COMMENT ON TABLE steam.game_genres IS 'A game can carry several genres';

-- Genre lookups go genre -> game (the primary key covers game -> genre).
CREATE INDEX IF NOT EXISTS idx_game_genres_genre ON steam.game_genres (genre_id);

-- ---------------------------------------------------------------------------
-- 4. library_entries: the user's ownership of a game
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS steam.library_entries (
    library_id               BIGSERIAL    PRIMARY KEY,
    game_id                  BIGINT       NOT NULL UNIQUE
                             REFERENCES steam.games(game_id) ON DELETE CASCADE,
    play_minutes             BIGINT       NOT NULL DEFAULT 0
                             CHECK (play_minutes >= 0),
    acquisition_type         VARCHAR(16)  NOT NULL DEFAULT 'unknown'
                             CHECK (acquisition_type IN
                               ('unknown', 'paid', 'free_to_play', 'free_claimed', 'gift')),
    completion_status        VARCHAR(16)  NOT NULL DEFAULT 'unknown'
                             CHECK (completion_status IN
                               ('unknown', 'playing', 'completed', 'abandoned', 'not_applicable')),
    progress_percent         SMALLINT     CHECK (progress_percent BETWEEN 0 AND 100),
    purchase_records_complete BOOLEAN     NOT NULL DEFAULT FALSE,
    is_hidden                BOOLEAN      NOT NULL DEFAULT FALSE,
    last_synced_at           TIMESTAMP,
    created_at               TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at               TIMESTAMP    NOT NULL DEFAULT now()
);

COMMENT ON TABLE  steam.library_entries IS 'One ownership row per game; unique game_id prevents duplicates';
COMMENT ON COLUMN steam.library_entries.acquisition_type IS 'How THIS user obtained it, distinct from games.is_free_to_play';
COMMENT ON COLUMN steam.library_entries.purchase_records_complete IS 'FALSE = cost totals must be labelled incomplete';
COMMENT ON COLUMN steam.library_entries.progress_percent IS 'User-maintained; never inferred from play time';

-- ---------------------------------------------------------------------------
-- 5. purchases: many purchase records per library entry
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS steam.purchases (
    purchase_id    BIGSERIAL      PRIMARY KEY,
    library_id     BIGINT         NOT NULL
                   REFERENCES steam.library_entries(library_id) ON DELETE CASCADE,
    purchase_date  DATE,
    paid_amount    NUMERIC(10, 2) NOT NULL CHECK (paid_amount >= 0),
    purchase_type  VARCHAR(8)     NOT NULL DEFAULT 'base'
                   CHECK (purchase_type IN ('base', 'dlc')),
    status         VARCHAR(8)     NOT NULL DEFAULT 'paid'
                   CHECK (status IN ('paid', 'refunded')),
    notes          TEXT,
    created_at     TIMESTAMP      NOT NULL DEFAULT now(),
    updated_at     TIMESTAMP      NOT NULL DEFAULT now()
);

COMMENT ON TABLE  steam.purchases IS 'Recorded purchases only; absence does NOT imply zero cost';
COMMENT ON COLUMN steam.purchases.paid_amount IS 'CNY only in v1.0; refunded rows are excluded from net spend';

-- Yearly spend trend filters and groups by purchase_date.
CREATE INDEX IF NOT EXISTS idx_purchases_date ON steam.purchases (purchase_date);

-- openGauss in A-compatibility mode maps DATE to timestamp(0), which keeps a
-- time-of-day component that a purchase "date" must not have. This constraint
-- pins the column to day granularity regardless of the stored type.
ALTER TABLE steam.purchases DROP CONSTRAINT IF EXISTS purchases_purchase_date_day_ck;
ALTER TABLE steam.purchases ADD CONSTRAINT purchases_purchase_date_day_ck
    CHECK (purchase_date = date_trunc('day', purchase_date));

-- ---------------------------------------------------------------------------
-- 6. sync_logs: independent log of each Steam sync attempt
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS steam.sync_logs (
    sync_id          BIGSERIAL    PRIMARY KEY,
    sync_started_at  TIMESTAMP    NOT NULL DEFAULT now(),
    sync_finished_at TIMESTAMP,
    status           VARCHAR(16)  NOT NULL DEFAULT 'running'
                     CHECK (status IN ('running', 'success', 'failed')),
    fetched_count    INTEGER      NOT NULL DEFAULT 0
                     CHECK (fetched_count >= 0),
    message          TEXT
);

COMMENT ON TABLE steam.sync_logs IS 'Sync history; deliberately has no game FK so partial failures still log';
