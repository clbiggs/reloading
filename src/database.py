"""Database initialization and configuration."""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

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


def _add_column_if_missing(conn, db_path, table_name, column_name, ddl):
    """Add a column when absent, tolerating concurrent startup races."""
    if column_name in _get_table_columns(db_path, table_name):
        return
    try:
        conn.execute(ddl)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


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
        if "factory_ammo_id" not in cols:
            conn.execute(
                "ALTER TABLE order_lots ADD COLUMN factory_ammo_id VARCHAR REFERENCES factory_ammo(id)"
            )

    # Migration: add optional measurement fields to factory_ammo
    if _table_exists(db_path, "factory_ammo"):
        cols = _get_table_columns(db_path, "factory_ammo")
        if "overall_length" not in cols:
            conn.execute("ALTER TABLE factory_ammo ADD COLUMN overall_length FLOAT")
        if "g1_bc" not in cols:
            conn.execute("ALTER TABLE factory_ammo ADD COLUMN g1_bc FLOAT")
        if "g7_bc" not in cols:
            conn.execute("ALTER TABLE factory_ammo ADD COLUMN g7_bc FLOAT")

    # Migration: add casing_lot_id and rounds_made to loads
    if _table_exists(db_path, "loads"):
        cols = _get_table_columns(db_path, "loads")
        if "casing_lot_id" not in cols:
            conn.execute(
                "ALTER TABLE loads ADD COLUMN casing_lot_id VARCHAR REFERENCES order_lots(id)"
            )
        if "rounds_made" not in cols:
            conn.execute("ALTER TABLE loads ADD COLUMN rounds_made INTEGER")

    # Migration: add recipe_id and discarded component fields to loads
    if _table_exists(db_path, "loads"):
        cols = _get_table_columns(db_path, "loads")
        if "recipe_id" not in cols:
            conn.execute(
                "ALTER TABLE loads ADD COLUMN recipe_id VARCHAR REFERENCES recipes(id)"
            )
        if "discarded_bullet" not in cols:
            conn.execute("ALTER TABLE loads ADD COLUMN discarded_bullet INTEGER")
        if "discarded_powder" not in cols:
            conn.execute("ALTER TABLE loads ADD COLUMN discarded_powder FLOAT")
        if "discarded_primer" not in cols:
            conn.execute("ALTER TABLE loads ADD COLUMN discarded_primer INTEGER")
        if "discarded_casing" not in cols:
            conn.execute("ALTER TABLE loads ADD COLUMN discarded_casing INTEGER")

    # Migration: add status flags to recipes
    if _table_exists(db_path, "recipes"):
        cols = _get_table_columns(db_path, "recipes")
        if "is_testing" not in cols:
            conn.execute(
                "ALTER TABLE recipes ADD COLUMN is_testing BOOLEAN NOT NULL DEFAULT 0"
            )
        if "is_abandoned" not in cols:
            conn.execute(
                "ALTER TABLE recipes ADD COLUMN is_abandoned BOOLEAN NOT NULL DEFAULT 0"
            )

    # Migration: add factory_ammo_lot_id to test_sessions
    if _table_exists(db_path, "test_sessions"):
        cols = _get_table_columns(db_path, "test_sessions")
        _add_column_if_missing(
            conn,
            db_path,
            "test_sessions",
            "factory_ammo_lot_id",
            "ALTER TABLE test_sessions ADD COLUMN factory_ammo_lot_id VARCHAR REFERENCES order_lots(id)",
        )
        # Note: old casing_id column is left in place if it exists,
        # as SQLite cannot drop columns with FK constraints.
        # SQLAlchemy will simply ignore the unmapped column.

    conn.commit()
    conn.close()


def _generate_uuid():
    return str(uuid.uuid4())


def _build_legacy_recipe_name(conn, load_row):
    """Build a descriptive recipe name from a legacy load's components."""
    parts = []

    bullet_desc = conn.execute(
        """
        SELECT bm.name || ' ' || b.model || ' (' || CAST(b.weight AS TEXT) || 'gr)'
        FROM bullets b
        JOIN manufacturers bm ON b.manufacturer_id = bm.id
        WHERE b.id = ?
        """,
        (load_row["bullet_id"],),
    ).fetchone()
    if bullet_desc:
        parts.append(bullet_desc[0])

    powder_desc = conn.execute(
        """
        SELECT pm.name || ' ' || p.name
        FROM powders p
        JOIN manufacturers pm ON p.manufacturer_id = pm.id
        WHERE p.id = ?
        """,
        (load_row["powder_id"],),
    ).fetchone()
    powder_part = powder_desc[0] if powder_desc else None
    if powder_part and load_row["powder_weight"] is not None:
        weight = load_row["powder_weight"]
        weight_text = f"{weight:g}"
        parts.append(f"{powder_part} {weight_text}gr")
    elif powder_part:
        parts.append(powder_part)

    primer_desc = conn.execute(
        """
        SELECT prm.name || ' ' || pr.model
        FROM primers pr
        JOIN manufacturers prm ON pr.manufacturer_id = prm.id
        WHERE pr.id = ?
        """,
        (load_row["primer_id"],),
    ).fetchone()
    if primer_desc:
        parts.append(primer_desc[0])

    casing_desc = conn.execute(
        "SELECT name FROM casings WHERE id = ?",
        (load_row["casing_id"],),
    ).fetchone()
    if casing_desc:
        parts.append(casing_desc[0])

    if not parts:
        return None
    return " — ".join(parts)[:200]


def _migrate_loads_to_recipes(db_path):
    """Create recipes from legacy loads and link each load to its recipe.

    Loads are grouped by component selection and powder charge weight so
    identical legacy setups reuse a single recipe.
    """
    if not _table_exists(db_path, "loads") or not _table_exists(db_path, "recipes"):
        return

    load_cols = _get_table_columns(db_path, "loads")
    if "powder_weight" not in load_cols or "recipe_id" not in load_cols:
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        pending = conn.execute(
            """
            SELECT l.id, l.powder_weight,
                   bl.bullet_id AS bullet_id,
                   pl.powder_id AS powder_id,
                   prl.primer_id AS primer_id,
                   cl.casing_id AS casing_id
            FROM loads l
            LEFT JOIN order_lots bl ON l.bullet_lot_id = bl.id
            LEFT JOIN order_lots pl ON l.powder_lot_id = pl.id
            LEFT JOIN order_lots prl ON l.primer_lot_id = prl.id
            LEFT JOIN order_lots cl ON l.casing_lot_id = cl.id
            WHERE l.recipe_id IS NULL
            """
        ).fetchall()

        if not pending:
            return

        recipe_cache = {}
        name_counts = {}
        now = datetime.now(timezone.utc).isoformat()

        for row in pending:
            key = (
                row["bullet_id"],
                row["powder_id"],
                row["primer_id"],
                row["casing_id"],
                row["powder_weight"],
            )

            if key not in recipe_cache:
                name = _build_legacy_recipe_name(conn, row) or "Migrated Recipe"
                name_counts[name] = name_counts.get(name, 0) + 1
                if name_counts[name] > 1:
                    name = f"{name} ({name_counts[name]})"

                recipe_id = _generate_uuid()
                conn.execute(
                    """
                    INSERT INTO recipes (
                        id, name, bullet_id, powder_id, primer_id, casing_id,
                        powder_weight, notes, date_created
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recipe_id,
                        name,
                        key[0],
                        key[1],
                        key[2],
                        key[3],
                        key[4],
                        None,
                        now,
                    ),
                )
                recipe_cache[key] = recipe_id

            conn.execute(
                "UPDATE loads SET recipe_id = ? WHERE id = ?",
                (recipe_cache[key], row["id"]),
            )

        conn.commit()
    finally:
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

    # Convert legacy loads into recipes (after create_all makes the recipes table)
    _migrate_loads_to_recipes(db_path)

