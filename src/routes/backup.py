"""Routes for exporting and importing all application data."""

import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from models import (
    db,
    Caliber,
    PrimerType,
    Manufacturer,
    Primer,
    Bullet,
    Casing,
    Powder,
    FactoryAmmo,
    OrderLot,
    Load,
    Firearm,
    TestSession,
    Shot,
)

bp = Blueprint("backup", __name__, url_prefix="/backup")

# Models in dependency order for export/import
MODELS_IN_ORDER = [
    ("calibers", Caliber),
    ("primer_types", PrimerType),
    ("manufacturers", Manufacturer),
    ("primers", Primer),
    ("bullets", Bullet),
    ("casings", Casing),
    ("powders", Powder),
    ("factory_ammo", FactoryAmmo),
    ("order_lots", OrderLot),
    ("loads", Load),
    ("firearms", Firearm),
    ("test_sessions", TestSession),
    ("shots", Shot),
]


def _serialize_value(value):
    """Convert a value to a JSON-serializable type."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _model_to_dict(instance):
    """Convert a SQLAlchemy model instance to a dict of column values."""
    return {
        col.name: _serialize_value(getattr(instance, col.name))
        for col in instance.__table__.columns
    }


def _parse_datetime(value):
    """Parse an ISO format datetime string back to a datetime object."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return value


@bp.route("/")
def index():
    """Show the backup/restore page."""
    counts = {}
    for key, model in MODELS_IN_ORDER:
        counts[key] = model.query.count()
    return render_template("backup/index.html", counts=counts)


@bp.route("/export")
def export():
    """Export all data as a JSON file download."""
    data = {"_meta": {
        "app": "reloading-tracker",
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }}

    for key, model in MODELS_IN_ORDER:
        data[key] = [_model_to_dict(row) for row in model.query.all()]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"reloading_backup_{timestamp}.json"

    return Response(
        json.dumps(data, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/import", methods=["POST"])
def import_data():
    """Import data from a JSON backup file, replacing all existing data."""
    if "file" not in request.files:
        flash("No file selected.", "danger")
        return redirect(url_for("backup.index"))

    file = request.files["file"]
    if not file.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("backup.index"))

    if not file.filename.endswith(".json"):
        flash("File must be a .json file.", "danger")
        return redirect(url_for("backup.index"))

    try:
        data = json.loads(file.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        flash(f"Invalid JSON file: {e}", "danger")
        return redirect(url_for("backup.index"))

    # Validate the file has the expected meta key
    if "_meta" not in data or data["_meta"].get("app") != "reloading-tracker":
        flash("This does not appear to be a valid Reloading Tracker backup file.", "danger")
        return redirect(url_for("backup.index"))

    try:
        # Delete all existing data in reverse dependency order
        for key, model in reversed(MODELS_IN_ORDER):
            model.query.delete()
        db.session.flush()

        # Import data in dependency order
        total_imported = 0
        for key, model in MODELS_IN_ORDER:
            rows = data.get(key, [])
            for row_data in rows:
                # Parse datetime columns
                for col in model.__table__.columns:
                    if col.name in row_data and isinstance(col.type, db.DateTime):
                        row_data[col.name] = _parse_datetime(row_data[col.name])
                instance = model(**row_data)
                db.session.add(instance)
            total_imported += len(rows)

        db.session.commit()
        flash(f"Backup restored successfully. {total_imported} records imported.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Import failed: {e}", "danger")

    return redirect(url_for("backup.index"))

