"""Routes for managing loads."""

from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Load, Recipe, OrderLot, Bullet, Powder, Primer, Casing, Caliber

bp = Blueprint("loads", __name__, url_prefix="/loads")


def _get_lot_choices(load=None):
    """Get order lot choices, filtering out depleted lots unless already selected."""
    def _query_lots(component_type, current_lot_id=None):
        query = OrderLot.query.filter_by(component_type=component_type)
        if current_lot_id:
            # Show non-depleted lots plus the currently selected lot
            query = query.filter(
                db.or_(OrderLot.is_depleted == False, OrderLot.id == current_lot_id)
            )
        else:
            query = query.filter_by(is_depleted=False)
        return query.order_by(OrderLot.order_date.desc()).all()

    return {
        "bullet_lots": _query_lots("bullet", load.bullet_lot_id if load else None),
        "powder_lots": _query_lots("powder", load.powder_lot_id if load else None),
        "primer_lots": _query_lots("primer", load.primer_lot_id if load else None),
        "casing_lots": _query_lots("casing", load.casing_lot_id if load else None),
    }


def _get_recipe_choices(current_recipe_id=None):
    """Recipe choices for load forms; abandoned recipes are hidden unless
    they are the recipe already selected on the load being edited."""
    query = Recipe.query
    if current_recipe_id:
        query = query.filter(
            db.or_(Recipe.is_abandoned == False, Recipe.id == current_recipe_id)
        )
    else:
        query = query.filter(Recipe.is_abandoned == False)
    return query.order_by(Recipe.name).all()


@bp.route("/")
def index():
    # --- Filters ---
    bullet_id = request.args.get("bullet_id", "").strip()
    powder_id = request.args.get("powder_id", "").strip()
    primer_id = request.args.get("primer_id", "").strip()
    caliber_id = request.args.get("caliber_id", "").strip()

    query = Load.query.join(Recipe, Load.recipe_id == Recipe.id, isouter=True)

    if bullet_id:
        query = query.filter(Recipe.bullet_id == bullet_id)

    if powder_id:
        query = query.filter(Recipe.powder_id == powder_id)

    if primer_id:
        query = query.filter(Recipe.primer_id == primer_id)

    if caliber_id:
        query = query.join(
            Bullet, Recipe.bullet_id == Bullet.id, isouter=True
        ).filter(Bullet.caliber_id == caliber_id)

    # --- Sorting ---
    sort = request.args.get("sort", "date").strip()
    sort_dir = request.args.get("sort_dir", "desc").strip()
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    if sort == "cost":
        # Cost is a computed property; fetch all then sort in Python
        loads = query.all()
        reverse = sort_dir == "desc"
        loads.sort(
            key=lambda l: (l.cost_per_round is not None, l.cost_per_round or 0),
            reverse=reverse,
        )
    else:
        if sort == "powder_weight":
            order_col = Recipe.powder_weight
        else:
            # Default to date
            sort = "date"
            order_col = Load.date_created

        if sort_dir == "asc":
            query = query.order_by(db.asc(order_col))
        else:
            query = query.order_by(db.desc(order_col))
        loads = query.all()

    # --- Filter dropdown choices ---
    bullets = (
        Bullet.query.join(Bullet.manufacturer)
        .order_by(db.text("manufacturers.name"), Bullet.model)
        .all()
    )
    powders = (
        Powder.query.join(Powder.manufacturer)
        .order_by(db.text("manufacturers.name"), Powder.name)
        .all()
    )
    primers = (
        Primer.query.join(Primer.manufacturer)
        .order_by(db.text("manufacturers.name"), Primer.model)
        .all()
    )
    calibers = Caliber.query.order_by(Caliber.name).all()

    return render_template(
        "loads/index.html",
        loads=loads,
        bullets=bullets,
        powders=powders,
        primers=primers,
        calibers=calibers,
        current_filters={
            "bullet_id": bullet_id,
            "powder_id": powder_id,
            "primer_id": primer_id,
            "caliber_id": caliber_id,
        },
        current_sort=sort,
        current_sort_dir=sort_dir,
    )


@bp.route("/view/<string:id>")
def view(id):
    load = Load.query.get_or_404(id)
    return render_template("loads/view.html", load=load)


@bp.route("/add", methods=["GET", "POST"])
def add():
    lots = _get_lot_choices()
    recipes = _get_recipe_choices(request.args.get("recipe_id"))
    bullets = Bullet.query.join(Bullet.manufacturer).order_by(
        db.text("manufacturers.name"), Bullet.model, Bullet.weight
    ).all()
    powders = Powder.query.join(Powder.manufacturer).order_by(
        db.text("manufacturers.name"), Powder.name
    ).all()
    primers = Primer.query.join(Primer.manufacturer).order_by(
        db.text("manufacturers.name"), Primer.model
    ).all()
    casings = Casing.query.order_by(Casing.name).all()

    if request.method == "POST":
        recipe = _get_recipe_from_form()
        data = _get_form_data() if recipe else None
        if recipe is None or data is None:
            return render_template(
                "loads/form.html",
                load=None,
                recipes=recipes,
                bullets=bullets,
                powders=powders,
                primers=primers,
                casings=casings,
                **lots,
            )
        load = Load(recipe_id=recipe.id, **data)
        db.session.add(load)
        db.session.commit()
        flash("Load added.", "success")
        return redirect(url_for("loads.index"))
    return render_template(
        "loads/form.html",
        load=None,
        recipes=recipes,
        bullets=bullets,
        powders=powders,
        primers=primers,
        casings=casings,
        **lots,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    load = Load.query.get_or_404(id)
    lots = _get_lot_choices(load)
    recipes = _get_recipe_choices(load.recipe_id)
    bullets = Bullet.query.join(Bullet.manufacturer).order_by(
        db.text("manufacturers.name"), Bullet.model, Bullet.weight
    ).all()
    powders = Powder.query.join(Powder.manufacturer).order_by(
        db.text("manufacturers.name"), Powder.name
    ).all()
    primers = Primer.query.join(Primer.manufacturer).order_by(
        db.text("manufacturers.name"), Primer.model
    ).all()
    casings = Casing.query.order_by(Casing.name).all()

    if request.method == "POST":
        recipe = _get_recipe_from_form()
        data = _get_form_data() if recipe else None
        if recipe is None or data is None:
            return render_template(
                "loads/form.html",
                load=load,
                recipes=recipes,
                bullets=bullets,
                powders=powders,
                primers=primers,
                casings=casings,
                **lots,
            )
        load.recipe_id = recipe.id
        for key, value in data.items():
            setattr(load, key, value)
        db.session.commit()
        flash("Load updated.", "success")
        return redirect(url_for("loads.index"))
    return render_template(
        "loads/form.html",
        load=load,
        recipes=recipes,
        bullets=bullets,
        powders=powders,
        primers=primers,
        casings=casings,
        **lots,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    load = Load.query.get_or_404(id)
    db.session.delete(load)
    db.session.commit()
    flash("Load deleted.", "success")
    return redirect(url_for("loads.index"))


def _get_recipe_from_form():
    """Resolve the recipe for a load from the form.

    Either selects an existing recipe or creates a new one inline.
    Returns None (after flashing an error) when validation fails.
    """
    mode = request.form.get("recipe_mode", "existing").strip()

    if mode == "new":
        name = request.form.get("new_recipe_name", "").strip()
        if not name:
            flash("Recipe name is required when creating a new recipe.", "danger")
            return None

        recipe = Recipe(name=name)

        powder_weight = request.form.get("new_powder_weight", "").strip()
        if powder_weight:
            try:
                recipe.powder_weight = round(float(powder_weight), 2)
            except ValueError:
                flash("Powder weight must be a number.", "danger")
                return None

        for field in ("bullet_id", "powder_id", "primer_id", "casing_id"):
            value = request.form.get(f"new_{field}", "").strip()
            if value:
                setattr(recipe, field, value)

        db.session.add(recipe)
        db.session.flush()
        return recipe

    recipe_id = request.form.get("recipe_id", "").strip()
    if not recipe_id:
        flash("Select an existing recipe or choose to create a new one.", "danger")
        return None

    recipe = Recipe.query.get(recipe_id)
    if recipe is None:
        flash("Selected recipe no longer exists.", "danger")
        return None

    return recipe


def _get_form_data():
    """Extract and validate load form data."""
    data = {}

    bullet_lot_id = request.form.get("bullet_lot_id", "").strip()
    data["bullet_lot_id"] = bullet_lot_id if bullet_lot_id else None

    powder_lot_id = request.form.get("powder_lot_id", "").strip()
    data["powder_lot_id"] = powder_lot_id if powder_lot_id else None

    primer_lot_id = request.form.get("primer_lot_id", "").strip()
    data["primer_lot_id"] = primer_lot_id if primer_lot_id else None

    casing_lot_id = request.form.get("casing_lot_id", "").strip()
    data["casing_lot_id"] = casing_lot_id if casing_lot_id else None

    for field, label, cast, precision in (
        ("discarded_bullet", "Discarded bullets", int, None),
        ("discarded_powder", "Discarded powder", float, 2),
        ("discarded_primer", "Discarded primers", int, None),
        ("discarded_casing", "Discarded casings", int, None),
    ):
        raw = request.form.get(field, "").strip()
        if raw:
            try:
                value = cast(raw)
            except ValueError:
                flash(f"{label} must be a number.", "danger")
                return None
            if value < 0:
                flash(f"{label} cannot be negative.", "danger")
                return None
            data[field] = round(value, precision) if precision else value
        else:
            data[field] = None

    rounds_made = request.form.get("rounds_made", "").strip()
    if rounds_made:
        try:
            rounds_made_value = int(rounds_made)
        except ValueError:
            flash("Rounds made must be a whole number.", "danger")
            return None

        if rounds_made_value <= 0:
            flash("Rounds made must be greater than zero.", "danger")
            return None

        data["rounds_made"] = rounds_made_value
    else:
        data["rounds_made"] = None

    data["notes"] = request.form.get("notes", "").strip() or None

    overall_length = request.form.get("overall_length", "").strip()
    if overall_length:
        try:
            data["overall_length"] = round(float(overall_length), 4)
        except ValueError:
            flash("Overall length must be a number.", "danger")
            return None
    else:
        data["overall_length"] = None

    cbto = request.form.get("cbto", "").strip()
    if cbto:
        try:
            data["cbto"] = round(float(cbto), 4)
        except ValueError:
            flash("CBTO must be a number.", "danger")
            return None
    else:
        data["cbto"] = None

    date_created_str = request.form.get("date_created", "").strip()
    if date_created_str:
        try:
            data["date_created"] = datetime.strptime(date_created_str, "%Y-%m-%d")
        except ValueError:
            flash("Invalid date format.", "danger")
            return None
    else:
        data["date_created"] = datetime.now(timezone.utc)

    return data
