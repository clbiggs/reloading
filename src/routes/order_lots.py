"""Routes for managing order lots."""

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, OrderLot, Bullet, Powder, Primer, Casing

bp = Blueprint("order_lots", __name__, url_prefix="/order-lots")


def _get_components():
    """Get all component lists for forms."""
    return {
        "bullets": Bullet.query.join(Bullet.manufacturer).order_by(Bullet.model).all(),
        "powders": Powder.query.join(Powder.manufacturer).order_by(Powder.name).all(),
        "primers": Primer.query.join(Primer.manufacturer).order_by(Primer.model).all(),
        "casings": Casing.query.order_by(Casing.name).all(),
    }


@bp.route("/")
def index():
    # --- Filters ---
    component_type = request.args.get("component_type", "").strip()
    status = request.args.get("status", "").strip()
    store = request.args.get("store", "").strip()

    query = OrderLot.query

    if component_type in ("bullet", "powder", "primer", "casing"):
        query = query.filter(OrderLot.component_type == component_type)

    if status == "available":
        query = query.filter(OrderLot.is_depleted == False)
    elif status == "depleted":
        query = query.filter(OrderLot.is_depleted == True)

    if store:
        query = query.filter(OrderLot.store == store)

    # --- Sorting ---
    sort = request.args.get("sort", "date").strip()
    sort_dir = request.args.get("sort_dir", "desc").strip()
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    if sort == "component":
        # component_display is a computed property; sort in Python
        order_lots = query.all()
        reverse = sort_dir == "desc"
        order_lots.sort(key=lambda ol: ol.component_display.lower(), reverse=reverse)
    else:
        sort_map = {
            "lot_number": OrderLot.lot_number,
            "quantity": OrderLot.quantity,
            "cost": OrderLot.total_cost,
        }
        if sort in sort_map:
            order_col = sort_map[sort]
        else:
            sort = "date"
            order_col = OrderLot.order_date

        if sort_dir == "asc":
            query = query.order_by(db.asc(order_col))
        else:
            query = query.order_by(db.desc(order_col))
        order_lots = query.all()

    # --- Filter dropdown choices ---
    stores = (
        db.session.query(OrderLot.store)
        .filter(OrderLot.store.isnot(None), OrderLot.store != "")
        .distinct()
        .order_by(OrderLot.store)
        .all()
    )
    store_list = [s[0] for s in stores]

    return render_template(
        "order_lots/index.html",
        order_lots=order_lots,
        store_list=store_list,
        current_filters={
            "component_type": component_type,
            "status": status,
            "store": store,
        },
        current_sort=sort,
        current_sort_dir=sort_dir,
    )


@bp.route("/add", methods=["GET", "POST"])
def add():
    components = _get_components()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "order_lots/form.html",
                order_lot=None,
                **components,
            )
        order_lot = OrderLot(**data)
        db.session.add(order_lot)
        db.session.commit()
        flash("Order lot added.", "success")
        return redirect(url_for("order_lots.index"))
    return render_template(
        "order_lots/form.html",
        order_lot=None,
        **components,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    order_lot = OrderLot.query.get_or_404(id)
    components = _get_components()
    if request.method == "POST":
        data = _get_form_data()
        if not data:
            return render_template(
                "order_lots/form.html",
                order_lot=order_lot,
                **components,
            )
        for key, value in data.items():
            setattr(order_lot, key, value)
        # Clear unrelated component references
        if data["component_type"] != "bullet":
            order_lot.bullet_id = None
        if data["component_type"] != "powder":
            order_lot.powder_id = None
        if data["component_type"] != "primer":
            order_lot.primer_id = None
        if data["component_type"] != "casing":
            order_lot.casing_id = None
        db.session.commit()
        flash("Order lot updated.", "success")
        return redirect(url_for("order_lots.index"))
    return render_template(
        "order_lots/form.html",
        order_lot=order_lot,
        **components,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    order_lot = OrderLot.query.get_or_404(id)
    db.session.delete(order_lot)
    db.session.commit()
    flash("Order lot deleted.", "success")
    return redirect(url_for("order_lots.index"))


@bp.route("/toggle-depleted/<string:id>", methods=["POST"])
def toggle_depleted(id):
    order_lot = OrderLot.query.get_or_404(id)
    order_lot.is_depleted = not order_lot.is_depleted
    db.session.commit()
    status = "depleted" if order_lot.is_depleted else "available"
    flash(f"Order lot marked as {status}.", "success")
    return redirect(url_for("order_lots.index"))


def _get_form_data():
    """Extract and validate order lot form data."""
    order_date_str = request.form.get("order_date", "").strip()
    store = request.form.get("store", "").strip()
    lot_number = request.form.get("lot_number", "").strip()
    total_cost = request.form.get("total_cost", "").strip()
    quantity = request.form.get("quantity", "").strip()
    component_type = request.form.get("component_type", "").strip()

    if not order_date_str or not quantity or not component_type:
        flash("Order date, quantity, and component type are required.", "danger")
        return None

    try:
        order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
    except ValueError:
        flash("Invalid date format.", "danger")
        return None

    try:
        quantity_val = int(quantity)
    except ValueError:
        flash("Quantity must be a whole number.", "danger")
        return None

    data = {
        "order_date": order_date,
        "store": store or None,
        "lot_number": lot_number or None,
        "quantity": quantity_val,
        "component_type": component_type,
    }

    if total_cost:
        try:
            data["total_cost"] = round(float(total_cost), 2)
        except ValueError:
            flash("Total cost must be a number.", "danger")
            return None

    # Set component reference based on type
    component_id = request.form.get("component_id", "").strip()
    if not component_id:
        flash("A component must be selected.", "danger")
        return None

    if component_type == "bullet":
        data["bullet_id"] = component_id
    elif component_type == "powder":
        data["powder_id"] = component_id
    elif component_type == "primer":
        data["primer_id"] = component_id
    elif component_type == "casing":
        data["casing_id"] = component_id
    else:
        flash("Invalid component type.", "danger")
        return None

    return data

