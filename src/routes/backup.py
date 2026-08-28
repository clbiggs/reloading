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
    Recipe,
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
    ("recipes", Recipe),
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
        "version": "2.0",
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
        legacy_load_powder_weights = {}
        has_recipes_key = "recipes" in data
        for key, model in MODELS_IN_ORDER:
            rows = data.get(key, [])
            for row_data in rows:
                # Capture legacy charge weights from pre-recipe backups
                if key == "loads" and "powder_weight" in row_data:
                    legacy_load_powder_weights[row_data.get("id")] = row_data.get(
                        "powder_weight"
                    )

                # Parse datetime columns and drop columns unknown to this schema
                clean_data = {}
                for col in model.__table__.columns:
                    if col.name not in row_data:
                        continue
                    value = row_data[col.name]
                    if value is not None and isinstance(col.type, db.DateTime):
                        value = _parse_datetime(value)
                    clean_data[col.name] = value
                instance = model(**clean_data)
                db.session.add(instance)
            total_imported += len(rows)

        # Legacy backups (before recipes existed) need recipes derived from loads
        if legacy_load_powder_weights and not has_recipes_key:
            db.session.flush()
            _create_recipes_for_legacy_loads(legacy_load_powder_weights)

        db.session.commit()
        flash(f"Backup restored successfully. {total_imported} records imported.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Import failed: {e}", "danger")

    return redirect(url_for("backup.index"))


def _create_recipes_for_legacy_loads(powder_weight_map):
    """Create recipes for loads from a pre-recipe backup and link them.

    Loads are grouped by component selection and powder charge weight so
    identical legacy setups reuse a single recipe.
    """
    recipe_cache = {}
    name_counts = {}

    for load in Load.query.filter(Load.recipe_id.is_(None)).all():
        powder_weight = powder_weight_map.get(load.id)
        bullet = load.bullet_lot.bullet if load.bullet_lot else None
        powder = load.powder_lot.powder if load.powder_lot else None
        primer = load.primer_lot.primer if load.primer_lot else None
        casing = load.casing_lot.casing if load.casing_lot else None

        key = (
            bullet.id if bullet else None,
            powder.id if powder else None,
            primer.id if primer else None,
            casing.id if casing else None,
            powder_weight,
        )

        if key not in recipe_cache:
            recipe = Recipe(
                name=_build_legacy_recipe_name(
                    bullet, powder, primer, casing, powder_weight, name_counts
                ),
                bullet_id=key[0],
                powder_id=key[1],
                primer_id=key[2],
                casing_id=key[3],
                powder_weight=powder_weight,
            )
            db.session.add(recipe)
            db.session.flush()
            recipe_cache[key] = recipe.id

        load.recipe_id = recipe_cache[key]


def _build_legacy_recipe_name(bullet, powder, primer, casing, powder_weight, name_counts):
    """Build a descriptive recipe name from a legacy load's components."""
    parts = []

    if bullet:
        parts.append(
            f"{bullet.manufacturer.name} {bullet.model} ({bullet.weight:g}gr)"
        )

    if powder:
        powder_desc = f"{powder.manufacturer.name} {powder.name}"
        if powder_weight is not None:
            parts.append(f"{powder_desc} {powder_weight:g}gr")
        else:
            parts.append(powder_desc)

    if primer:
        parts.append(f"{primer.manufacturer.name} {primer.model}")

    if casing:
        parts.append(casing.name)

    name = " — ".join(parts)[:200] if parts else "Migrated Recipe"
    name_counts[name] = name_counts.get(name, 0) + 1
    if name_counts[name] > 1:
        name = f"{name} ({name_counts[name]})"
    return name

