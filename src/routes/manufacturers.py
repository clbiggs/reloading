"""Routes for managing manufacturers."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Manufacturer

bp = Blueprint("manufacturers", __name__, url_prefix="/manufacturers")


@bp.route("/")
def index():
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    return render_template("manufacturers/index.html", manufacturers=manufacturers)


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Manufacturer name is required.", "danger")
            return render_template("manufacturers/form.html", manufacturer=None)
        if Manufacturer.query.filter_by(name=name).first():
            flash("Manufacturer already exists.", "danger")
            return render_template("manufacturers/form.html", manufacturer=None)
        mfg = Manufacturer(name=name)
        db.session.add(mfg)
        db.session.commit()
        flash(f"Manufacturer '{name}' added.", "success")
        return redirect(url_for("manufacturers.index"))
    return render_template("manufacturers/form.html", manufacturer=None)


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    manufacturer = Manufacturer.query.get_or_404(id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Manufacturer name is required.", "danger")
            return render_template(
                "manufacturers/form.html", manufacturer=manufacturer
            )
        existing = Manufacturer.query.filter_by(name=name).first()
        if existing and existing.id != manufacturer.id:
            flash("Manufacturer already exists.", "danger")
            return render_template(
                "manufacturers/form.html", manufacturer=manufacturer
            )
        manufacturer.name = name
        db.session.commit()
        flash("Manufacturer updated.", "success")
        return redirect(url_for("manufacturers.index"))
    return render_template("manufacturers/form.html", manufacturer=manufacturer)


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    manufacturer = Manufacturer.query.get_or_404(id)
    db.session.delete(manufacturer)
    db.session.commit()
    flash(f"Manufacturer '{manufacturer.name}' deleted.", "success")
    return redirect(url_for("manufacturers.index"))

