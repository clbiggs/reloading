"""Routes for managing primers."""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Primer, Manufacturer, PrimerType

bp = Blueprint("primers", __name__, url_prefix="/primers")


@bp.route("/")
def index():
    primers = Primer.query.join(Manufacturer).order_by(Manufacturer.name, Primer.model).all()
    return render_template("primers/index.html", primers=primers)


@bp.route("/add", methods=["GET", "POST"])
def add():
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    primer_types = PrimerType.query.order_by(PrimerType.name).all()
    if request.method == "POST":
        manufacturer_id = request.form.get("manufacturer_id")
        model = request.form.get("model", "").strip()
        primer_type_id = request.form.get("primer_type_id")
        if not manufacturer_id or not model or not primer_type_id:
            flash("All fields are required.", "danger")
            return render_template(
                "primers/form.html",
                primer=None,
                manufacturers=manufacturers,
                primer_types=primer_types,
            )
        primer = Primer(
            manufacturer_id=manufacturer_id,
            model=model,
            primer_type_id=int(primer_type_id),
        )
        db.session.add(primer)
        db.session.commit()
        flash("Primer added.", "success")
        return redirect(url_for("primers.index"))
    return render_template(
        "primers/form.html",
        primer=None,
        manufacturers=manufacturers,
        primer_types=primer_types,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    primer = Primer.query.get_or_404(id)
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    primer_types = PrimerType.query.order_by(PrimerType.name).all()
    if request.method == "POST":
        manufacturer_id = request.form.get("manufacturer_id")
        model = request.form.get("model", "").strip()
        primer_type_id = request.form.get("primer_type_id")
        if not manufacturer_id or not model or not primer_type_id:
            flash("All fields are required.", "danger")
            return render_template(
                "primers/form.html",
                primer=primer,
                manufacturers=manufacturers,
                primer_types=primer_types,
            )
        primer.manufacturer_id = manufacturer_id
        primer.model = model
        primer.primer_type_id = int(primer_type_id)
        db.session.commit()
        flash("Primer updated.", "success")
        return redirect(url_for("primers.index"))
    return render_template(
        "primers/form.html",
        primer=primer,
        manufacturers=manufacturers,
        primer_types=primer_types,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    primer = Primer.query.get_or_404(id)
    db.session.delete(primer)
    db.session.commit()
    flash("Primer deleted.", "success")
    return redirect(url_for("primers.index"))

