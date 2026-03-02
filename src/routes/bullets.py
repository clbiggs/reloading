"""Routes for managing bullets."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Bullet, Manufacturer, Caliber

bp = Blueprint("bullets", __name__, url_prefix="/bullets")


@bp.route("/")
def index():
    bullets = Bullet.query.join(Manufacturer).order_by(Manufacturer.name, Bullet.model).all()
    return render_template("bullets/index.html", bullets=bullets)


@bp.route("/add", methods=["GET", "POST"])
def add():
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    calibers = Caliber.query.order_by(Caliber.name).all()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "bullets/form.html",
                bullet=None,
                manufacturers=manufacturers,
                calibers=calibers,
            )
        bullet = Bullet(**data)
        db.session.add(bullet)
        db.session.commit()
        flash("Bullet added.", "success")
        return redirect(url_for("bullets.index"))
    return render_template(
        "bullets/form.html",
        bullet=None,
        manufacturers=manufacturers,
        calibers=calibers,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    bullet = Bullet.query.get_or_404(id)
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    calibers = Caliber.query.order_by(Caliber.name).all()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "bullets/form.html",
                bullet=bullet,
                manufacturers=manufacturers,
                calibers=calibers,
            )
        for key, value in data.items():
            setattr(bullet, key, value)
        db.session.commit()
        flash("Bullet updated.", "success")
        return redirect(url_for("bullets.index"))
    return render_template(
        "bullets/form.html",
        bullet=bullet,
        manufacturers=manufacturers,
        calibers=calibers,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    bullet = Bullet.query.get_or_404(id)
    db.session.delete(bullet)
    db.session.commit()
    flash("Bullet deleted.", "success")
    return redirect(url_for("bullets.index"))


def _get_form_data():
    """Extract and validate bullet form data."""
    manufacturer_id = request.form.get("manufacturer_id")
    model = request.form.get("model", "").strip()
    weight = request.form.get("weight", "").strip()
    caliber_id = request.form.get("caliber_id")

    if not manufacturer_id or not model or not weight or not caliber_id:
        flash("Manufacturer, model, weight, and caliber are required.", "danger")
        return None

    try:
        weight_val = round(float(weight), 2)
    except ValueError:
        flash("Weight must be a number.", "danger")
        return None

    data = {
        "manufacturer_id": manufacturer_id,
        "model": model,
        "weight": weight_val,
        "caliber_id": int(caliber_id),
    }

    overall_length = request.form.get("overall_length", "").strip()
    if overall_length:
        try:
            data["overall_length"] = round(float(overall_length), 4)
        except ValueError:
            flash("Overall length must be a number.", "danger")
            return None

    g7_bc = request.form.get("g7_bc", "").strip()
    if g7_bc:
        try:
            data["g7_bc"] = float(g7_bc)
        except ValueError:
            flash("G7 BC must be a number.", "danger")
            return None

    g1_bc = request.form.get("g1_bc", "").strip()
    if g1_bc:
        try:
            data["g1_bc"] = float(g1_bc)
        except ValueError:
            flash("G1 BC must be a number.", "danger")
            return None

    return data

