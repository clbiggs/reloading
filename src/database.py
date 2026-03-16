"""Database initialization and configuration."""

import os
import sqlite3

from models import db


def _get_table_columns(db_path, table_name):
    """Return a set of column names for a given table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    return columns


def _table_exists(db_path, table_name):
    """Check if a table exists in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def _run_migrations(db_path):
    """Run schema migrations for existing databases."""
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)

    # Migration: add is_depleted to order_lots
    if _table_exists(db_path, "order_lots"):
        cols = _get_table_columns(db_path, "order_lots")
        if "is_depleted" not in cols:
            conn.execute(
                "ALTER TABLE order_lots ADD COLUMN is_depleted BOOLEAN DEFAULT 0"
            )
        if "casing_id" not in cols:
            conn.execute(
                "ALTER TABLE order_lots ADD COLUMN casing_id VARCHAR REFERENCES casings(id)"
            )

    # Migration: add casing_lot_id to loads
    if _table_exists(db_path, "loads"):
        cols = _get_table_columns(db_path, "loads")
        if "casing_lot_id" not in cols:
            conn.execute(
                "ALTER TABLE loads ADD COLUMN casing_lot_id VARCHAR REFERENCES order_lots(id)"
            )
        # Note: old casing_id column is left in place if it exists,
        # as SQLite cannot drop columns with FK constraints.
        # SQLAlchemy will simply ignore the unmapped column.

    conn.commit()
    conn.close()


def init_db(app):
    """Initialize the database with the Flask app."""
    db_path = os.environ.get("DATABASE_PATH", "/data/reloading.db")
    # Ensure the directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Run schema migrations before initializing SQLAlchemy
    _run_migrations(db_path)

    db.init_app(app)

    with app.app_context():
        db.create_all()

