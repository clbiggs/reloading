"""Routes for managing factory ammo."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, FactoryAmmo, Manufacturer, Caliber

bp = Blueprint("factory_ammo", __name__, url_prefix="/factory-ammo")


@bp.route("/")
def index():
    factory_ammo = (
        FactoryAmmo.query.join(Manufacturer)
        .join(Caliber)
        .order_by(Manufacturer.name, Caliber.name, FactoryAmmo.weight)
        .all()
    )
    return render_template("factory_ammo/index.html", factory_ammo=factory_ammo)


@bp.route("/add", methods=["GET", "POST"])
def add():
    manufacturers, calibers = _get_form_choices()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "factory_ammo/form.html",
                ammo=None,
                manufacturers=manufacturers,
                calibers=calibers,
            )
        ammo = FactoryAmmo(**data)
        db.session.add(ammo)
        db.session.commit()
        flash("Factory ammo added.", "success")
        return redirect(url_for("factory_ammo.index"))
    return render_template(
        "factory_ammo/form.html",
        ammo=None,
        manufacturers=manufacturers,
        calibers=calibers,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    ammo = FactoryAmmo.query.get_or_404(id)
    manufacturers, calibers = _get_form_choices()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "factory_ammo/form.html",
                ammo=ammo,
                manufacturers=manufacturers,
                calibers=calibers,
            )
        for key, value in data.items():
            setattr(ammo, key, value)
        db.session.commit()
        flash("Factory ammo updated.", "success")
        return redirect(url_for("factory_ammo.index"))
    return render_template(
        "factory_ammo/form.html",
        ammo=ammo,
        manufacturers=manufacturers,
        calibers=calibers,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    ammo = FactoryAmmo.query.get_or_404(id)
    db.session.delete(ammo)
    db.session.commit()
    flash("Factory ammo deleted.", "success")
    return redirect(url_for("factory_ammo.index"))


def _get_form_choices():
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    calibers = Caliber.query.order_by(Caliber.name).all()
    return manufacturers, calibers


def _get_form_data():
    """Extract and validate factory ammo form data."""
    manufacturer_id = request.form.get("manufacturer_id", "").strip()
    caliber_id = request.form.get("caliber_id", "").strip()
    weight = request.form.get("weight", "").strip()
    bullet_style = request.form.get("bullet_style", "").strip()
    muzzle_velocity = request.form.get("muzzle_velocity", "").strip()
    bullet_brand = request.form.get("bullet_brand", "").strip()
    overall_length = request.form.get("overall_length", "").strip()
    g1_bc = request.form.get("g1_bc", "").strip()
    g7_bc = request.form.get("g7_bc", "").strip()

    if not all(
        [manufacturer_id, caliber_id, weight, bullet_style, muzzle_velocity, bullet_brand]
    ):
        flash(
            "Manufacturer, caliber, weight, bullet style, muzzle velocity, and bullet brand are required.",
            "danger",
        )
        return None

    try:
        weight_val = round(float(weight), 2)
    except ValueError:
        flash("Weight must be a number.", "danger")
        return None

    try:
        muzzle_velocity_val = round(float(muzzle_velocity), 2)
    except ValueError:
        flash("Muzzle velocity must be a number.", "danger")
        return None

    data = {
        "manufacturer_id": manufacturer_id,
        "caliber_id": int(caliber_id),
        "weight": weight_val,
        "bullet_style": bullet_style,
        "muzzle_velocity": muzzle_velocity_val,
        "bullet_brand": bullet_brand,
        "overall_length": None,
        "g1_bc": None,
        "g7_bc": None,
    }

    if overall_length:
        try:
            data["overall_length"] = round(float(overall_length), 4)
        except ValueError:
            flash("Overall length must be a number.", "danger")
            return None

    if g1_bc:
        try:
            data["g1_bc"] = float(g1_bc)
        except ValueError:
            flash("G1 BC must be a number.", "danger")
            return None

    if g7_bc:
        try:
            data["g7_bc"] = float(g7_bc)
        except ValueError:
            flash("G7 BC must be a number.", "danger")
            return None

    return data
