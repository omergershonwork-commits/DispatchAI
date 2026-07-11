from sqlalchemy import create_engine, inspect, text

from app.db.schema_migrations import ensure_runtime_schema


def test_runtime_schema_adds_dashboard_columns_to_legacy_tables() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE incidents ("
                "id INTEGER PRIMARY KEY, "
                "summary TEXT NOT NULL, "
                "people_count INTEGER"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE volunteers ("
                "id INTEGER PRIMARY KEY, "
                "source VARCHAR(32), "
                "source_chat_id INTEGER, "
                "status VARCHAR(32), "
                "metadata_json JSON"
                ")"
            )
        )

    ensure_runtime_schema(engine)

    inspector = inspect(engine)
    incident_columns = {column["name"] for column in inspector.get_columns("incidents")}
    volunteer_columns = {column["name"] for column in inspector.get_columns("volunteers")}

    assert {"title", "casualties_text"}.issubset(incident_columns)
    assert {
        "phone_number",
        "gender",
        "height_cm",
        "weight_kg",
        "trust_score",
        "inventory",
    }.issubset(volunteer_columns)
