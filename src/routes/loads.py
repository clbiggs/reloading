"""Routes for managing loads/recipes."""

from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Load, OrderLot

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
    loads = Load.query.order_by(Load.date_created.desc()).all()
    return render_template("loads/index.html", loads=loads)


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

