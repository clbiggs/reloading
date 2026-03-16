"""Routes for managing powders."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Powder, Manufacturer

bp = Blueprint("powders", __name__, url_prefix="/powders")


@bp.route("/")
def index():
    powders = Powder.query.join(Manufacturer).order_by(Manufacturer.name, Powder.name).all()
    return render_template("powders/index.html", powders=powders)


@bp.route("/add", methods=["GET", "POST"])
def add():
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    if request.method == "POST":
        manufacturer_id = request.form.get("manufacturer_id")
        name = request.form.get("name", "").strip()
        if not manufacturer_id or not name:
            flash("Manufacturer and name are required.", "danger")
            return render_template(
                "powders/form.html", powder=None, manufacturers=manufacturers
            )
        powder = Powder(manufacturer_id=manufacturer_id, name=name)
        db.session.add(powder)
        db.session.commit()
        flash("Powder added.", "success")
        return redirect(url_for("powders.index"))
    return render_template(
        "powders/form.html", powder=None, manufacturers=manufacturers
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    powder = Powder.query.get_or_404(id)
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    if request.method == "POST":
        manufacturer_id = request.form.get("manufacturer_id")
        name = request.form.get("name", "").strip()
        if not manufacturer_id or not name:
            flash("Manufacturer and name are required.", "danger")
            return render_template(
                "powders/form.html", powder=powder, manufacturers=manufacturers
            )
        powder.manufacturer_id = manufacturer_id
        powder.name = name
        db.session.commit()
        flash("Powder updated.", "success")
        return redirect(url_for("powders.index"))
    return render_template(
        "powders/form.html", powder=powder, manufacturers=manufacturers
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    powder = Powder.query.get_or_404(id)
    db.session.delete(powder)
    db.session.commit()
    flash("Powder deleted.", "success")
    return redirect(url_for("powders.index"))

