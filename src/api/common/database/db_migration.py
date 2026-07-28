"""
Database migration module.
Creates all required tables and loads sample data when the database is empty.
Migration is idempotent — safe to call multiple times.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

_SAMPLE_DATA_PATHS = [
    "/app/data/sample_processed_data.json",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sample_processed_data.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "infra", "data", "sample_processed_data.json"),
]

_CREATE_PROCESSED_DATA = """
CREATE TABLE processed_data (
    ConversationId varchar(255) NOT NULL PRIMARY KEY,
    EndTime varchar(255),
    StartTime varchar(255),
    Content varchar(max),
    summary varchar(3000),
    satisfied varchar(50),
    sentiment varchar(50),
    mined_topic varchar(500),
    key_phrases varchar(1000),
    complaint varchar(500)
)
"""

_CREATE_PROCESSED_DATA_KEY_PHRASES = """
CREATE TABLE processed_data_key_phrases (
    id int IDENTITY(1,1) PRIMARY KEY,
    ConversationId varchar(255),
    topic varchar(500),
    key_phrase varchar(500),
    sentiment varchar(50),
    StartTime varchar(255)
)
"""

_CREATE_KM_MINED_TOPICS = """
CREATE TABLE km_mined_topics (
    id int IDENTITY(1,1) PRIMARY KEY,
    topic varchar(500) NOT NULL,
    display_name varchar(500)
)
"""

_CREATE_KM_PROCESSED_DATA = """
CREATE TABLE km_processed_data (
    ConversationId varchar(255) NOT NULL PRIMARY KEY,
    EndTime varchar(255),
    StartTime varchar(255),
    Content varchar(max),
    summary varchar(3000),
    satisfied varchar(50),
    sentiment varchar(50),
    topic varchar(500),
    keyphrases varchar(1000),
    complaint varchar(500)
)
"""

_TABLES = [
    ("processed_data", _CREATE_PROCESSED_DATA),
    ("processed_data_key_phrases", _CREATE_PROCESSED_DATA_KEY_PHRASES),
    ("km_mined_topics", _CREATE_KM_MINED_TOPICS),
    ("km_processed_data", _CREATE_KM_PROCESSED_DATA),
]


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_NAME = ?",
        table_name,
    )
    return cursor.fetchone()[0] > 0


def ensure_tables_exist(cursor, conn) -> bool:
    """
    Creates all required tables if they do not exist.
    Returns True if tables were created, False if they already existed.
    """
    if _table_exists(cursor, "km_processed_data"):
        logger.info("Tables already exist — skipping DDL.")
        return False

    logger.info("Tables not found — running DDL migration.")
    for table_name, ddl in _TABLES:
        if not _table_exists(cursor, table_name):
            logger.info("Creating table: %s", table_name)
            cursor.execute(ddl)
            conn.commit()
        else:
            logger.info("Table already exists, skipping: %s", table_name)

    return True


def _load_sample_json() -> list:
    for path in _SAMPLE_DATA_PATHS:
        resolved = os.path.normpath(path)
        if os.path.isfile(resolved):
            logger.info("Loading sample data from: %s", resolved)
            with open(resolved, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        "sample_processed_data.json not found. Searched: " + ", ".join(_SAMPLE_DATA_PATHS)
    )


def load_sample_data(cursor, conn) -> int:
    """
    Inserts sample data into all tables.
    Returns the number of records inserted into processed_data.
    """
    records = _load_sample_json()
    logger.info("Inserting %d records into processed_data.", len(records))

    insert_pd = (
        "INSERT INTO processed_data "
        "(ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, "
        "mined_topic, key_phrases, complaint) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    for rec in records:
        cursor.execute(
            insert_pd,
            rec.get("ConversationId"),
            rec.get("EndTime"),
            rec.get("StartTime"),
            rec.get("Content"),
            rec.get("summary"),
            rec.get("satisfied"),
            rec.get("sentiment"),
            rec.get("mined_topic"),
            rec.get("key_phrases"),
            rec.get("complaint"),
        )
    conn.commit()
    logger.info("processed_data loaded.")

    insert_kp = (
        "INSERT INTO processed_data_key_phrases "
        "(ConversationId, topic, key_phrase, sentiment, StartTime) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    kp_count = 0
    for rec in records:
        raw_phrases = rec.get("key_phrases", "") or ""
        phrases = [p.strip() for p in raw_phrases.split(",") if p.strip()]
        for phrase in phrases:
            cursor.execute(
                insert_kp,
                rec.get("ConversationId"),
                rec.get("mined_topic"),
                phrase,
                rec.get("sentiment"),
                rec.get("StartTime"),
            )
            kp_count += 1
    conn.commit()
    logger.info("processed_data_key_phrases loaded (%d rows).", kp_count)

    seen_topics: set = set()
    insert_topic = "INSERT INTO km_mined_topics (topic, display_name) VALUES (?, ?)"
    for rec in records:
        topic = rec.get("mined_topic")
        if topic and topic not in seen_topics:
            seen_topics.add(topic)
            cursor.execute(insert_topic, topic, topic)
    conn.commit()
    logger.info("km_mined_topics loaded (%d rows).", len(seen_topics))

    cursor.execute(
        "INSERT INTO km_processed_data "
        "SELECT ConversationId, EndTime, StartTime, Content, summary, satisfied, sentiment, "
        "mined_topic AS topic, key_phrases AS keyphrases, complaint "
        "FROM processed_data"
    )
    conn.commit()
    logger.info("km_processed_data populated.")

    return len(records)


def run_migration(conn) -> str:
    """
    Orchestrates the full migration: creates tables and loads sample data if needed.
    Returns a human-readable status message.
    """
    cursor = conn.cursor()
    try:
        created = ensure_tables_exist(cursor, conn)
        if not created:
            cursor.execute("SELECT COUNT(*) FROM km_processed_data")
            row_count = cursor.fetchone()[0]
            if row_count > 0:
                return f"Tables already exist with {row_count} records — no migration needed."
            logger.info("Tables exist but are empty — loading sample data.")
        else:
            logger.info("Tables created — loading sample data.")

        count = load_sample_data(cursor, conn)
        return f"Migration complete. {count} records loaded into all tables."
    finally:
        cursor.close()
