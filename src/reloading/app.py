import json
import os
from decimal import Decimal

import pandas as pd
import plotly
import plotly.express as px
from flask import Flask, flash, redirect, render_template, request, url_for
from sqlalchemy import String, asc, cast, desc, func, or_

from database import (
    Bullet,
    Cartridge,
    Firearm,
    Load,
    Powder,
    Shot,
    TestResult,
    TestSession,
    db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "reloading_secret_key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
db.init_app(app)


@app.route("/")
def index():
    # Filtering Logic
    f_id = request.args.get("f_id")
    b_id = request.args.get("b_id")
    p_id = request.args.get("p_id")

    full_bullet_name = func.concat(Bullet.manufacturer, " ", Bullet.model)
    full_firearm_name = func.concat(Firearm.make, " ", Firearm.model)
    full_powder_name = func.concat(Powder.manufacturer, " ", Powder.name)

    query = (
        db.session.query(
            Shot.velocity_fps,
            Load.powder_weight_grains,
            full_firearm_name.label("firearm_name"),
            full_bullet_name.label("bullet_name"),
        )
        .select_from(Shot)
        .join(TestResult, Shot.result_id == TestResult.result_id)
        .join(Load, TestResult.load_id == Load.load_id)
        .join(Bullet, Load.bullet_id == Bullet.bullet_id)
        .join(TestSession, TestResult.session_id == TestSession.session_id)
        .join(Firearm, TestSession.firearm_id == Firearm.firearm_id)
    )

    # Apply Filters if they exist
    if f_id and f_id != "":
        query = query.filter(Firearm.id == f_id)
    if b_id and b_id != "":
        query = query.filter(Bullet.id == b_id)
    if p_id and p_id != "":
        query = query.filter(Load.powder_id == p_id)

    df = pd.read_sql(query.statement, db.engine)

    chart_json = None
    if not df.empty:
        fig = px.scatter(
            df,
            x="powder_weight_grains",
            y="velocity_fps",
            color="firearm_name",
            hover_data=["bullet_name"],
            title="Charge Weight vs Velocity",
            labels={
                "powder_weight_grains": "Powder Charge (gr)",
                "velocity_fps": "Velocity (fps)",
            },
            template="plotly_white",
        )
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    firearms = Firearm.query.all()
    bullets = Bullet.query.all()
    powders = Powder.query.all()
    results = (
        db.session.query(
            full_firearm_name.label("firearm_name"),
            TestSession.test_date,
            TestSession.session_id,
            TestSession.temperature_f,
            TestSession.location,
            full_bullet_name.label("bullet_name"),
            full_powder_name.label("powder_name"),
        )
        .select_from(TestResult)
        .join(TestSession, TestResult.session_id == TestSession.session_id)
        .join(Firearm, TestSession.firearm_id == Firearm.firearm_id)
        .join(Load, TestResult.load_id == Load.load_id)
        .join(Bullet, Load.bullet_id == Bullet.bullet_id)
        .all()
    )

    return render_template(
        "index.html",
        chart_json=chart_json,
        firearms=firearms,
        bullets=bullets,
        powders=powders,
        results=results,
    )


# --- FIREARM LIST ---
@app.route("/firearms")
def list_firearms():
    # Get parameters from URL
    search = request.args.get("search", "")
    sort = request.args.get("sort", "make")
    order = request.args.get("order", "asc")

    # Start the base query
    query = Firearm.query

    if search:
        query = query.filter(
            or_(
                Firearm.make.ilike(f"%{search}%"),
                Firearm.model.ilike(f"%{search}%"),
                cast(Firearm.caliber, String).ilike(f"%{search}%"),
            )
        )

    sort_colum = getattr(Firearm, sort, Firearm.make)
    if order == "desc":
        query = query.order_by(desc(sort_colum))
    else:
        query = query.order_by(asc(sort_colum))

    firearms = query.all()

    return render_template(
        "firearms/list.html",
        firearms=firearms,
        search=search,
        current_sort=sort,
        current_order=order,
    )


# --- ADD FIREARM ---
@app.route("/firearms/add", methods=["GET", "POST"])
def add_firearm():
    if request.method == "POST":
        new_f = Firearm(
            make=request.form["make"],
            model=request.form["model"],
            caliber=request.form["caliber"],
            barrel_length=request.form["barrel_length"],
            twist_rate=request.form["twist_rate"],
            notes=request.form["notes"],
        )
        db.session.add(new_f)
        db.session.commit()
        flash("Firearm added successfully!")
        return redirect(url_for("list_firearms"))
    return render_template("firearms/form.html", firearm=None)


# --- EDIT FIREARM ---
@app.route("/firearms/edit/<int:fid>", methods=["GET", "POST"])
def edit_firearm(fid):
    f = Firearm.query.get_or_404(fid)
    if request.method == "POST":
        f.make = request.form["make"]
        f.model = request.form["model"]
        f.caliber = request.form["caliber"]
        f.barrel_length = request.form["barrel_length"]
        f.twist_rate = request.form["twist_rate"]
        f.notes = request.form["notes"]
        db.session.commit()
        return redirect(url_for("list_firearms"))
    return render_template("firearms/form.html", firearm=f)


# --- DELETE FIREARM ---
@app.route("/firearms/delete/<int:fid>", methods=["POST"])
def delete_firearm(fid):
    #    f = Firearm.query.get_or_404(fid)
    #    db.session.delete(f)
    #    db.session.commit()
    flash("Firearm removed." + fid)
    return redirect(url_for("list_firearms"))


# --- FIREARM DETAILS & ANALYTICS ---
@app.route("/firearm/<int:fid>")
def firearm_detail(fid):
    f = Firearm.query.get_or_404(fid)

    full_bullet_name = func.concat(Bullet.manufacturer, " ", Bullet.model)
    full_powder_name = func.concat(Powder.manufacturer, " ", Powder.name)

    # 1. Fetch Sessions for this Firearm
    sessions = (
        TestSession.query.filter_by(firearm_id=fid)
        .order_by(TestSession.test_date.desc())
        .all()
    )

    # 2. Analytics Query: Get all shots associated with this firearm
    query = (
        db.session.query(
            Shot.velocity_fps,
            Load.powder_weight_grains,
            TestResult.group_size_moa,
            full_bullet_name.label("bullet_name"),
            full_powder_name.label("powder_name"),
            (full_bullet_name + "<br>" + full_powder_name).label("full_name"),
        )
        .select_from(TestResult)
        .join(TestSession, TestResult.session_id == TestSession.session_id)
        .join(Firearm, TestSession.firearm_id == Firearm.firearm_id)
        .join(Load, TestResult.load_id == Load.load_id)
        .join(Bullet, Load.bullet_id == Bullet.bullet_id)
        .join(Shot, TestResult.result_id == Shot.result_id)
        .join(Powder, Load.powder_id == Powder.powder_id)
        .filter(Firearm.firearm_id == fid)
    )

    df = pd.read_sql(query.statement, db.engine)

    chart_json = None
    summary = {"best_moa": "N/A", "avg_fps": "N/A", "total_shots": 0}

    if not df.empty:
        # Summary stats
        summary["best_moa"] = df["group_size_moa"].min()
        summary["avg_fps"] = round(df["velocity_fps"].mean(), 1)
        summary["total_shots"] = len(df)

        # Graph: Velocity Ladder for this specific rifle
        fig = px.scatter(
            df,
            x="powder_weight_grains",
            y="velocity_fps",
            color="full_name",
            title=f"Load Performance: {f.make} {f.model}",
            labels={
                "powder_weight_grains": "Charge (gr)",
                "velocity_fps": "Velocity (fps)",
                "full_name": "Load Name",
            },
            template="plotly_white",
            trendline="ols",
        )
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template(
        "firearms/detail.html",
        firearm=f,
        sessions=sessions,
        chart_json=chart_json,
        summary=summary,
    )


# --- BULLET LIST ---
@app.route("/bullets")
def list_bullets():
    # Get parameters from URL
    search = request.args.get("search", "")
    sort = request.args.get("sort", "manufacturer")
    order = request.args.get("order", "asc")

    # Start the base query
    query = Bullet.query

    if search:
        query = query.filter(
            or_(
                Bullet.manufacturer.ilike(f"%{search}%"),
                Bullet.model.ilike(f"%{search}%"),
                cast(Bullet.weight_grains, String).ilike(f"%{search}%"),
                cast(Bullet.caliber, String).ilike(f"%{search}%"),
            )
        )

    sort_colum = getattr(Bullet, sort, Bullet.manufacturer)
    if order == "desc":
        query = query.order_by(desc(sort_colum))
    else:
        query = query.order_by(asc(sort_colum))

    bullets = query.all()

    return render_template(
        "bullets/list.html",
        bullets=bullets,
        search=search,
        current_sort=sort,
        current_order=order,
    )


# --- ADD BULLET ---
@app.route("/bullets/add", methods=["GET", "POST"])
def add_bullet():
    if request.method == "POST":
        new_b = Bullet(
            manufacturer=request.form["manufacturer"],
            model=request.form["model"],
            weight_grains=request.form["weight_grains"],
            overall_length_inch=request.form["overall_length_inch"],
            caliber=request.form["caliber"],
            ballistic_coefficient_g7=request.form["ballistic_coefficient_g7"],
            ballistic_coefficient_g1=request.form["ballistic_coefficient_g1"],
        )
        db.session.add(new_b)
        db.session.commit()
        flash("Bullet added successfully!")
        return redirect(url_for("list_bullets"))
    return render_template("bullets/form.html", firearm=None)


# --- EDIT BULLET ---
@app.route("/bullets/edit/<int:bid>", methods=["GET", "POST"])
def edit_bullet(bid):
    b = Bullet.query.get_or_404(bid)
    if request.method == "POST":
        b.manufacturer = request.form["manufacturer"]
        b.model = request.form["model"]
        b.weight_grains = request.form["weight_grains"]
        b.overall_length_inch = request.form["overall_length_inch"]
        b.caliber = request.form["caliber"]
        b.ballistic_coefficient_g7 = request.form["ballistic_coefficient_g7"]
        b.ballistic_coefficient_g1 = request.form["ballistic_coefficient_g1"]
        db.session.commit()
        return redirect(url_for("list_bullets"))
    return render_template("bullets/form.html", bullet=b)


# --- DELETE BULLET ---
@app.route("/bullets/delete/<int:bid>", methods=["POST"])
def delete_bullet(bid):
    #    b = Bullet.query.get_or_404(bid)
    #    db.session.delete(b)
    #    db.session.commit()
    flash("Bullet removed." + bid)
    return redirect(url_for("list_bullets"))


# --- BULLET DETAILS & ANALYTICS ---
@app.route("/bullets/<int:bid>")
def bullet_detail(bid):
    b = Bullet.query.get_or_404(bid)

    loads = Load.query.filter_by(bullet_id=bid).all()

    results = []
    seen_firearm_ids = set()
    firearms = []
    seen_session_ids = set()

    for bullet_load in loads:
        for r in bullet_load.test_results:
            results.append(r)
            s = r.test_session
            seen_session_ids.add(s.session_id)
            if s.firearm and s.firearm.firearm_id not in seen_firearm_ids:
                firearms.append(s.firearm)
                seen_firearm_ids.add(s.firearm.firearm_id)

    results.sort(key=lambda x: x.test_session.test_date, reverse=True)
    firearms.sort(key=lambda f: f.make)

    return render_template(
        "bullets/detail.html",
        bullet=b,
        loads=loads,
        results=results,
        firearms=firearms,
        session_ids=seen_session_ids,
    )


# --- POWDER LIST ---
@app.route("/powders")
def list_powders():
    # Get parameters from URL
    search = request.args.get("search", "")
    sort = request.args.get("sort", "manufacturer")
    order = request.args.get("order", "asc")

    # Start the base query
    query = Powder.query

    if search:
        query = query.filter(
            or_(
                Powder.manufacturer.ilike(f"%{search}%"),
                Powder.model.ilike(f"%{search}%"),
                cast(Powder.weight_grains, String).ilike(f"%{search}%"),
                cast(Powder.caliber, String).ilike(f"%{search}%"),
            )
        )

    sort_colum = getattr(Powder, sort, Powder.manufacturer)
    if order == "desc":
        query = query.order_by(desc(sort_colum))
    else:
        query = query.order_by(asc(sort_colum))

    powders = query.all()

    return render_template(
        "powders/list.html",
        powders=powders,
        search=search,
        current_sort=sort,
        current_order=order,
    )


# --- ADD POWDER ---
@app.route("/powders/add", methods=["GET", "POST"])
def add_powder():
    if request.method == "POST":
        new_p = Powder(
            manufacturer=request.form["manufacturer"],
            name=request.form["name"],
        )
        db.session.add(new_p)
        db.session.commit()
        flash("Powder added successfully!")
        return redirect(url_for("list_powders"))
    return render_template("powders/form.html", powder=None)


# --- EDIT POWDER ---
@app.route("/powders/edit/<int:pid>", methods=["GET", "POST"])
def edit_powder(pid):
    p = Powder.query.get_or_404(pid)
    if request.method == "POST":
        p.manufacturer = request.form["manufacturer"]
        p.name = request.form["name"]
        db.session.commit()
        return redirect(url_for("list_powders"))
    return render_template("powders/form.html", powder=p)


# --- DELETE POWDER ---
@app.route("/powders/delete/<int:pid>", methods=["POST"])
def delete_powder(pid):
    #    p = Cartridge.query.get_or_404(pid)
    #    db.session.delete(p)
    #    db.session.commit()
    flash("Powder removed." + pid)
    return redirect(url_for("list_powders"))


# --- POWDER DETAILS ---
@app.route("/powders/<int:pid>")
def powder_detail(pid):
    powder = Powder.query.get_or_404(pid)

    results = []
    seen_firearm_ids = set()
    firearms = []
    seen_session_ids = set()
    loads = []

    for powder_load in powder.loads:
        loads.append(powder_load)
        for r in powder_load.test_results:
            results.append(r)
            s = r.test_session
            seen_session_ids.add(s.session_id)
            if s.firearm and s.firearm.firearm_id not in seen_firearm_ids:
                firearms.append(s.firearm)
                seen_firearm_ids.add(s.firearm.firearm_id)

    results.sort(key=lambda x: x.test_session.test_date, reverse=True)
    firearms.sort(key=lambda f: f.make)

    return render_template(
        "powders/detail.html",
        powder=powder,
        loads=loads,
        results=results,
        firearms=firearms,
        session_ids=seen_session_ids,
    )


# --- CARTRIDGES LIST ---
@app.route("/cartridges")
def list_cartridges():
    # Get parameters from URL
    search = request.args.get("search", "")
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")

    # Start the base query
    query = Cartridge.query

    if search:
        query = query.filter(
            or_(
                Cartridge.name.ilike(f"%{search}%"),
                Cartridge.primer_type.ilike(f"%{search}%"),
                cast(Cartridge.max_trim_length_in, String).ilike(f"%{search}%"),
                cast(Cartridge.max_coal_in, String).ilike(f"%{search}%"),
            )
        )

    sort_colum = getattr(Cartridge, sort, Cartridge.name)
    if order == "desc":
        query = query.order_by(desc(sort_colum))
    else:
        query = query.order_by(asc(sort_colum))

    cartridges = query.all()

    return render_template(
        "cartridges/list.html",
        cartridges=cartridges,
        search=search,
        current_sort=sort,
        current_order=order,
    )


# --- ADD CARTRIDGE ---
@app.route("/cartridges/add", methods=["GET", "POST"])
def add_cartridge():
    if request.method == "POST":
        new_c = Cartridge(
            name=request.form["name"],
            max_trim_length_in=request.form["max_trim_length_in"],
            max_coal_in=request.form["max_coal_in"],
            primer_type=request.form["primer_type"],
        )
        db.session.add(new_c)
        db.session.commit()
        flash("Cartridge added successfully!")
        return redirect(url_for("list_cartridges"))
    return render_template("cartridges/form.html", cartridge=None)


# --- EDIT CARTRIDGE ---
@app.route("/cartridges/edit/<int:cid>", methods=["GET", "POST"])
def edit_cartridge(cid):
    c = Cartridge.query.get_or_404(cid)
    if request.method == "POST":
        c.name = request.form["name"]
        c.max_trim_length_in = request.form["max_trim_length_in"]
        c.max_coal_in = request.form["max_coal_in"]
        c.primer_type = request.form["primer_type"]
        db.session.commit()
        return redirect(url_for("list_cartridges"))
    return render_template("cartridges/form.html", cartridge=c)


# --- DELETE CARTRIDGE ---
@app.route("/cartridges/delete/<int:cid>", methods=["POST"])
def delete_cartridge(cid):
    #    c = Cartridge.query.get_or_404(cid)
    #    db.session.delete(c)
    #    db.session.commit()
    flash("Cartridge removed." + cid)
    return redirect(url_for("list_cartridges"))


# --- CARTRIDGE DETAILS ---
@app.route("/cartridges/<int:cid>")
def cartridge_detail(cid):
    cartridge = Cartridge.query.get_or_404(cid)

    results = []
    seen_firearm_ids = set()
    firearms = []
    seen_session_ids = set()
    loads = []

    for cartridge_load in cartridge.loads:
        loads.append(cartridge_load)
        for r in cartridge_load.test_results:
            results.append(r)
            s = r.test_session
            seen_session_ids.add(s.session_id)
            if s.firearm and s.firearm.firearm_id not in seen_firearm_ids:
                firearms.append(s.firearm)
                seen_firearm_ids.add(s.firearm.firearm_id)

    results.sort(key=lambda x: x.test_session.test_date, reverse=True)
    firearms.sort(key=lambda f: f.make)

    return render_template(
        "cartridges/detail.html",
        cartridge=cartridge,
        loads=loads,
        results=results,
        firearms=firearms,
        session_ids=seen_session_ids,
    )


def format_numeric_caliber(val):
    if val is None:
        return ""

    if not isinstance(val, Decimal):
        val = Decimal(str(val))

    normalized_val = val.quantize(Decimal("0.000"))

    diameter_map = {
        Decimal("0.223"): "5.56mm",
        Decimal("0.224"): "5.56mm",
        Decimal("0.243"): "6mm",
        Decimal("0.264"): "6.5mm",
        Decimal("0.277"): "6.8mm",
        Decimal("0.284"): "7mm",
        Decimal("0.308"): "7.62mm",
        Decimal("0.311"): "7.62mm Rus",
        Decimal("0.355"): "9mm",
        Decimal("0.356"): "9mm",
        Decimal("0.357"): "9mm / .38 cal",
        Decimal("0.400"): "10mm",
        Decimal("0.500"): "12.7mm",
    }

    formatted_str = f"{normalized_val:f}".lstrip("0")

    if not formatted_str or formatted_str.startswith(""):
        if not formatted_str.startswith("."):
            formatted_str = f"0{formatted_str}" if formatted_str else "0"

    metric = diameter_map.get(normalized_val)

    return f"{formatted_str} ({metric})" if metric else formatted_str


app.jinja_env.filters["display_caliber"] = format_numeric_caliber

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", debug=True)
