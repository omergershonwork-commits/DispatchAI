from collections.abc import Mapping

from sqlalchemy import Engine, inspect, text

from app.db.session import Base

ADDITIVE_COLUMNS: Mapping[str, Mapping[str, str]] = {
    "incidents": {
        "title": "VARCHAR(160)",
        "casualties_text": "TEXT",
    },
    "volunteers": {
        "phone_number": "VARCHAR(64)",
        "gender": "VARCHAR(32)",
        "height_cm": "DOUBLE PRECISION",
        "weight_kg": "DOUBLE PRECISION",
        "trust_score": "DOUBLE PRECISION DEFAULT 0.5",
        "inventory": "JSON",
    },
}


def ensure_runtime_schema(engine: Engine) -> None:
    """Create known tables and add approved nullable columns to older databases."""

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, columns in ADDITIVE_COLUMNS.items():
            if table_name not in table_names:
                continue
            existing_columns = {
                column["name"] for column in inspect(connection).get_columns(table_name)
            }
            for column_name, column_type in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(
                    text(
                        f'ALTER TABLE "{table_name}" '
                        f'ADD COLUMN "{column_name}" {column_type}'
                    )
                )

        if "volunteers" in table_names:
            connection.execute(
                text("UPDATE volunteers SET trust_score = 0.5 WHERE trust_score IS NULL")
            )
