"""Routes for managing primer types."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, PrimerType

bp = Blueprint("primer_types", __name__, url_prefix="/primer-types")


@bp.route("/")
def index():
    primer_types = PrimerType.query.order_by(PrimerType.name).all()
    return render_template("primer_types/index.html", primer_types=primer_types)


@bp.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Primer type name is required.", "danger")
            return render_template("primer_types/form.html", primer_type=None)
        if PrimerType.query.filter_by(name=name).first():
            flash("Primer type already exists.", "danger")
            return render_template("primer_types/form.html", primer_type=None)
        pt = PrimerType(name=name)
        db.session.add(pt)
        db.session.commit()
        flash(f"Primer type '{name}' added.", "success")
        return redirect(url_for("primer_types.index"))
    return render_template("primer_types/form.html", primer_type=None)


@bp.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    primer_type = PrimerType.query.get_or_404(id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Primer type name is required.", "danger")
            return render_template("primer_types/form.html", primer_type=primer_type)
        existing = PrimerType.query.filter_by(name=name).first()
        if existing and existing.id != primer_type.id:
            flash("Primer type already exists.", "danger")
            return render_template("primer_types/form.html", primer_type=primer_type)
        primer_type.name = name
        db.session.commit()
        flash("Primer type updated.", "success")
        return redirect(url_for("primer_types.index"))
    return render_template("primer_types/form.html", primer_type=primer_type)


@bp.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    primer_type = PrimerType.query.get_or_404(id)
    db.session.delete(primer_type)
    db.session.commit()
    flash(f"Primer type '{primer_type.name}' deleted.", "success")
    return redirect(url_for("primer_types.index"))

