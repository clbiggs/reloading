"""Routes for managing calibers."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Caliber

bp = Blueprint("calibers", __name__, url_prefix="/calibers")


@bp.route("/")
def index():
    calibers = Caliber.query.order_by(Caliber.name).all()
    return render_template("calibers/index.html", calibers=calibers)


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Caliber name is required.", "danger")
            return render_template("calibers/form.html", caliber=None)
        if Caliber.query.filter_by(name=name).first():
            flash("Caliber already exists.", "danger")
            return render_template("calibers/form.html", caliber=None)
        caliber = Caliber(name=name)
        db.session.add(caliber)
        db.session.commit()
        flash(f"Caliber '{name}' added.", "success")
        return redirect(url_for("calibers.index"))
    return render_template("calibers/form.html", caliber=None)


@bp.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    caliber = Caliber.query.get_or_404(id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Caliber name is required.", "danger")
            return render_template("calibers/form.html", caliber=caliber)
        existing = Caliber.query.filter_by(name=name).first()
        if existing and existing.id != caliber.id:
            flash("Caliber already exists.", "danger")
            return render_template("calibers/form.html", caliber=caliber)
        caliber.name = name
        db.session.commit()
        flash(f"Caliber updated.", "success")
        return redirect(url_for("calibers.index"))
    return render_template("calibers/form.html", caliber=caliber)


@bp.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    caliber = Caliber.query.get_or_404(id)
    db.session.delete(caliber)
    db.session.commit()
    flash(f"Caliber '{caliber.name}' deleted.", "success")
    return redirect(url_for("calibers.index"))

