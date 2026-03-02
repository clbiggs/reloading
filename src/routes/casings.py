"""Routes for managing casings."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Casing, PrimerType

bp = Blueprint("casings", __name__, url_prefix="/casings")


@bp.route("/")
def index():
    casings = Casing.query.order_by(Casing.name).all()
    return render_template("casings/index.html", casings=casings)


@bp.route("/add", methods=["GET", "POST"])
def add():
    primer_types = PrimerType.query.order_by(PrimerType.name).all()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "casings/form.html", casing=None, primer_types=primer_types
            )
        casing = Casing(**data)
        db.session.add(casing)
        db.session.commit()
        flash("Casing added.", "success")
        return redirect(url_for("casings.index"))
    return render_template("casings/form.html", casing=None, primer_types=primer_types)


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    casing = Casing.query.get_or_404(id)
    primer_types = PrimerType.query.order_by(PrimerType.name).all()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "casings/form.html", casing=casing, primer_types=primer_types
            )
        for key, value in data.items():
            setattr(casing, key, value)
        db.session.commit()
        flash("Casing updated.", "success")
        return redirect(url_for("casings.index"))
    return render_template(
        "casings/form.html", casing=casing, primer_types=primer_types
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    casing = Casing.query.get_or_404(id)
    db.session.delete(casing)
    db.session.commit()
    flash(f"Casing '{casing.name}' deleted.", "success")
    return redirect(url_for("casings.index"))


def _get_form_data():
    """Extract and validate casing form data."""
    name = request.form.get("name", "").strip()
    primer_type_id = request.form.get("primer_type_id")

    if not name or not primer_type_id:
        flash("Name and primer type are required.", "danger")
        return None

    data = {
        "name": name,
        "primer_type_id": int(primer_type_id),
    }

    max_trim_length = request.form.get("max_trim_length", "").strip()
    if max_trim_length:
        try:
            data["max_trim_length"] = round(float(max_trim_length), 4)
        except ValueError:
            flash("Max trim length must be a number.", "danger")
            return None

    overall_length = request.form.get("overall_length", "").strip()
    if overall_length:
        try:
            data["overall_length"] = round(float(overall_length), 4)
        except ValueError:
            flash("Overall length must be a number.", "danger")
            return None

    return data

