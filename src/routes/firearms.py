"""Routes for managing firearms."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Firearm, Caliber

bp = Blueprint("firearms", __name__, url_prefix="/firearms")


@bp.route("/")
def index():
    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    return render_template("firearms/index.html", firearms=firearms)


@bp.route("/add", methods=["GET", "POST"])
def add():
    calibers = Caliber.query.order_by(Caliber.name).all()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "firearms/form.html", firearm=None, calibers=calibers
            )
        firearm = Firearm(**data)
        db.session.add(firearm)
        db.session.commit()
        flash("Firearm added.", "success")
        return redirect(url_for("firearms.index"))
    return render_template("firearms/form.html", firearm=None, calibers=calibers)


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    firearm = Firearm.query.get_or_404(id)
    calibers = Caliber.query.order_by(Caliber.name).all()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "firearms/form.html", firearm=firearm, calibers=calibers
            )
        for key, value in data.items():
            setattr(firearm, key, value)
        db.session.commit()
        flash("Firearm updated.", "success")
        return redirect(url_for("firearms.index"))
    return render_template(
        "firearms/form.html", firearm=firearm, calibers=calibers
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    firearm = Firearm.query.get_or_404(id)
    db.session.delete(firearm)
    db.session.commit()
    flash("Firearm deleted.", "success")
    return redirect(url_for("firearms.index"))


def _get_form_data():
    """Extract and validate firearm form data."""
    make = request.form.get("make", "").strip()
    model = request.form.get("model", "").strip()
    caliber_id = request.form.get("caliber_id")

    if not make or not model or not caliber_id:
        flash("Make, model, and caliber are required.", "danger")
        return None

    data = {
        "make": make,
        "model": model,
        "caliber_id": int(caliber_id),
    }

    barrel_length = request.form.get("barrel_length", "").strip()
    if barrel_length:
        try:
            data["barrel_length"] = round(float(barrel_length), 2)
        except ValueError:
            flash("Barrel length must be a number.", "danger")
            return None

    data["twist_rate"] = request.form.get("twist_rate", "").strip() or None
    data["notes"] = request.form.get("notes", "").strip() or None

    return data

