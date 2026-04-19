"""Routes for managing loads/recipes."""

from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Load, OrderLot, Bullet, Powder, Primer, Caliber

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


@bp.route("/")
def index():
    # --- Filters ---
    bullet_id = request.args.get("bullet_id", "").strip()
    powder_id = request.args.get("powder_id", "").strip()
    primer_id = request.args.get("primer_id", "").strip()
    caliber_id = request.args.get("caliber_id", "").strip()

    query = Load.query

    if bullet_id:
        query = query.join(
            OrderLot, Load.bullet_lot_id == OrderLot.id
        ).filter(OrderLot.bullet_id == bullet_id)

    if powder_id:
        powder_lot = db.aliased(OrderLot)
        query = query.join(
            powder_lot, Load.powder_lot_id == powder_lot.id
        ).filter(powder_lot.powder_id == powder_id)

    if primer_id:
        primer_lot = db.aliased(OrderLot)
        query = query.join(
            primer_lot, Load.primer_lot_id == primer_lot.id
        ).filter(primer_lot.primer_id == primer_id)

    if caliber_id:
        if not bullet_id:
            # Need to join bullet_lot if not already joined
            bullet_lot_cal = db.aliased(OrderLot)
            bullet_cal = db.aliased(Bullet)
            query = query.join(
                bullet_lot_cal, Load.bullet_lot_id == bullet_lot_cal.id
            ).join(
                bullet_cal, bullet_lot_cal.bullet_id == bullet_cal.id
            ).filter(bullet_cal.caliber_id == caliber_id)
        else:
            # Already joined OrderLot for bullet, just join Bullet
            query = query.join(
                Bullet, OrderLot.bullet_id == Bullet.id
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
            order_col = Load.powder_weight
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

    if request.method == "POST":
        data = _get_form_data()
        if data is None:
            return render_template(
                "loads/form.html",
                load=None,
                **lots,
            )
        load = Load(**data)
        db.session.add(load)
        db.session.commit()
        flash("Load/Recipe added.", "success")
        return redirect(url_for("loads.index"))
    return render_template(
        "loads/form.html",
        load=None,
        **lots,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    load = Load.query.get_or_404(id)
    lots = _get_lot_choices(load)

    if request.method == "POST":
        data = _get_form_data()
        if data is None:
            return render_template(
                "loads/form.html",
                load=load,
                **lots,
            )
        for key, value in data.items():
            setattr(load, key, value)
        db.session.commit()
        flash("Load/Recipe updated.", "success")
        return redirect(url_for("loads.index"))
    return render_template(
        "loads/form.html",
        load=load,
        **lots,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    load = Load.query.get_or_404(id)
    db.session.delete(load)
    db.session.commit()
    flash("Load/Recipe deleted.", "success")
    return redirect(url_for("loads.index"))


def _get_form_data():
    """Extract and validate load form data."""
    data = {}

    bullet_lot_id = request.form.get("bullet_lot_id", "").strip()
    data["bullet_lot_id"] = bullet_lot_id if bullet_lot_id else None

    powder_lot_id = request.form.get("powder_lot_id", "").strip()
    data["powder_lot_id"] = powder_lot_id if powder_lot_id else None

    powder_weight = request.form.get("powder_weight", "").strip()
    if powder_weight:
        try:
            data["powder_weight"] = round(float(powder_weight), 2)
        except ValueError:
            flash("Powder weight must be a number.", "danger")
            return None
    else:
        data["powder_weight"] = None

    primer_lot_id = request.form.get("primer_lot_id", "").strip()
    data["primer_lot_id"] = primer_lot_id if primer_lot_id else None

    casing_lot_id = request.form.get("casing_lot_id", "").strip()
    data["casing_lot_id"] = casing_lot_id if casing_lot_id else None

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

