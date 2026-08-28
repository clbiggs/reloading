"""Routes for managing recipes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Recipe, Bullet, Powder, Primer, Casing, Caliber, OrderLot

bp = Blueprint("recipes", __name__, url_prefix="/recipes")


def _get_component_choices():
    """Get component choices for recipe forms."""
    return {
        "bullets": (
            Bullet.query.join(Bullet.manufacturer)
            .order_by(db.text("manufacturers.name"), Bullet.model, Bullet.weight)
            .all()
        ),
        "powders": (
            Powder.query.join(Powder.manufacturer)
            .order_by(db.text("manufacturers.name"), Powder.name)
            .all()
        ),
        "primers": (
            Primer.query.join(Primer.manufacturer)
            .order_by(db.text("manufacturers.name"), Primer.model)
            .all()
        ),
        "casings": Casing.query.order_by(Casing.name).all(),
    }


@bp.route("/")
def index():
    # --- Filters ---
    name_filter = request.args.get("name", "").strip()
    bullet_id = request.args.get("bullet_id", "").strip()
    powder_id = request.args.get("powder_id", "").strip()
    primer_id = request.args.get("primer_id", "").strip()
    casing_id = request.args.get("casing_id", "").strip()
    caliber_id = request.args.get("caliber_id", "").strip()
    testing = request.args.get("testing", "").strip()
    abandoned = request.args.get("abandoned", "").strip()

    query = Recipe.query

    if name_filter:
        query = query.filter(Recipe.name.ilike(f"%{name_filter}%"))
    if bullet_id:
        query = query.filter(Recipe.bullet_id == bullet_id)
    if powder_id:
        query = query.filter(Recipe.powder_id == powder_id)
    if primer_id:
        query = query.filter(Recipe.primer_id == primer_id)
    if casing_id:
        query = query.filter(Recipe.casing_id == casing_id)
    if caliber_id:
        query = query.join(Bullet, Recipe.bullet_id == Bullet.id).filter(
            Bullet.caliber_id == caliber_id
        )
    if testing == "yes":
        query = query.filter(Recipe.is_testing == True)
    elif testing == "no":
        query = query.filter(Recipe.is_testing == False)
    if abandoned == "yes":
        query = query.filter(Recipe.is_abandoned == True)
    elif abandoned == "no":
        query = query.filter(Recipe.is_abandoned == False)

    # --- Sorting ---
    sort = request.args.get("sort", "name").strip()
    sort_dir = request.args.get("sort_dir", "asc").strip()
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    if sort == "powder_weight":
        order_col = Recipe.powder_weight
    elif sort == "date":
        order_col = Recipe.date_created
    elif sort == "load_count":
        # Load count is computed; sort in Python
        recipes = query.all()
        reverse = sort_dir == "desc"
        recipes.sort(key=lambda r: len(r.loads), reverse=reverse)
        sort = "load_count"
    else:
        sort = "name"
        order_col = Recipe.name

        if sort_dir == "asc":
            query = query.order_by(db.asc(order_col))
        else:
            query = query.order_by(db.desc(order_col))
        recipes = query.all()

    return render_template(
        "recipes/index.html",
        recipes=recipes,
        **_get_filter_choices(),
        current_filters={
            "name": name_filter,
            "bullet_id": bullet_id,
            "powder_id": powder_id,
            "primer_id": primer_id,
            "casing_id": casing_id,
            "caliber_id": caliber_id,
            "testing": testing,
            "abandoned": abandoned,
        },
        current_sort=sort,
        current_sort_dir=sort_dir,
    )


def _get_filter_choices():
    return {
        "bullets": (
            Bullet.query.join(Bullet.manufacturer)
            .order_by(db.text("manufacturers.name"), Bullet.model)
            .all()
        ),
        "powders": (
            Powder.query.join(Powder.manufacturer)
            .order_by(db.text("manufacturers.name"), Powder.name)
            .all()
        ),
        "primers": (
            Primer.query.join(Primer.manufacturer)
            .order_by(db.text("manufacturers.name"), Primer.model)
            .all()
        ),
        "casings": Casing.query.order_by(Casing.name).all(),
        "calibers": Caliber.query.order_by(Caliber.name).all(),
    }


@bp.route("/view/<string:id>")
def view(id):
    recipe = Recipe.query.get_or_404(id)
    loads = sorted(
        recipe.loads,
        key=lambda load: load.date_created,
        reverse=True,
    )

    component_lot_map = {}
    for component_type in ("bullet", "powder", "primer", "casing"):
        component_id = getattr(recipe, f"{component_type}_id")
        lots = []
        if component_id:
            lots = (
                OrderLot.query.filter_by(**{f"{component_type}_id": component_id})
                .order_by(OrderLot.order_date.desc())
                .all()
            )
        component_lot_map[component_type] = lots

    return render_template(
        "recipes/view.html",
        recipe=recipe,
        loads=loads,
        component_lot_map=component_lot_map,
    )


@bp.route("/add", methods=["GET", "POST"])
def add():
    components = _get_component_choices()
    if request.method == "POST":
        data = _get_form_data()
        if data is None:
            return render_template(
                "recipes/form.html",
                recipe=None,
                **components,
            )
        recipe = Recipe(**data)
        db.session.add(recipe)
        db.session.commit()
        flash("Recipe added.", "success")
        return redirect(url_for("recipes.view", id=recipe.id))
    return render_template(
        "recipes/form.html",
        recipe=None,
        **components,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    recipe = Recipe.query.get_or_404(id)
    components = _get_component_choices()
    if request.method == "POST":
        data = _get_form_data()
        if data is None:
            return render_template(
                "recipes/form.html",
                recipe=recipe,
                **components,
            )
        for key, value in data.items():
            setattr(recipe, key, value)
        db.session.commit()
        flash("Recipe updated.", "success")
        return redirect(url_for("recipes.view", id=recipe.id))
    return render_template(
        "recipes/form.html",
        recipe=recipe,
        **components,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    recipe = Recipe.query.get_or_404(id)
    if recipe.loads:
        flash(
            "Cannot delete this recipe because one or more loads use it.",
            "danger",
        )
        return redirect(url_for("recipes.view", id=recipe.id))
    db.session.delete(recipe)
    db.session.commit()
    flash("Recipe deleted.", "success")
    return redirect(url_for("recipes.index"))


def _get_form_data():
    """Extract and validate recipe form data."""
    data = {}

    name = request.form.get("name", "").strip()
    if not name:
        flash("Recipe name is required.", "danger")
        return None
    data["name"] = name

    for field in ("bullet_id", "powder_id", "primer_id", "casing_id"):
        value = request.form.get(field, "").strip()
        data[field] = value if value else None

    powder_weight = request.form.get("powder_weight", "").strip()
    if powder_weight:
        try:
            data["powder_weight"] = round(float(powder_weight), 2)
        except ValueError:
            flash("Powder weight must be a number.", "danger")
            return None
    else:
        data["powder_weight"] = None

    data["notes"] = request.form.get("notes", "").strip() or None

    data["is_testing"] = request.form.get("is_testing") == "on"
    data["is_abandoned"] = request.form.get("is_abandoned") == "on"

    return data
