"""Routes for managing test sessions and shots."""

import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, TestSession, Shot, Firearm, Load
from utils.calculations import calculate_density_altitude

bp = Blueprint("test_sessions", __name__, url_prefix="/test-sessions")


@bp.route("/")
def index():
    sessions = TestSession.query.order_by(TestSession.test_date.desc()).all()
    return render_template("test_sessions/index.html", sessions=sessions)


@bp.route("/view/<string:id>")
def view(id):
    session = TestSession.query.get_or_404(id)
    return render_template("test_sessions/view.html", session=session)


@bp.route("/add", methods=["GET", "POST"])
def add():
    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    loads = Load.query.order_by(Load.date_created.desc()).all()
    if request.method == "POST":
        data = _get_session_form_data()
        if data is None:
            return render_template(
                "test_sessions/form.html",
                session=None,
                firearms=firearms,
                loads=loads,
            )
        session = TestSession(**data)
        db.session.add(session)
        db.session.flush()

        # Process shots
        _save_shots(session.id, request.form)

        db.session.commit()
        flash("Test session added.", "success")
        return redirect(url_for("test_sessions.view", id=session.id))
    return render_template(
        "test_sessions/form.html",
        session=None,
        firearms=firearms,
        loads=loads,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    session = TestSession.query.get_or_404(id)
    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    loads = Load.query.order_by(Load.date_created.desc()).all()
    if request.method == "POST":
        data = _get_session_form_data()
        if data is None:
            return render_template(
                "test_sessions/form.html",
                session=session,
                firearms=firearms,
                loads=loads,
            )
        for key, value in data.items():
            setattr(session, key, value)

        # Delete existing shots and re-add
        Shot.query.filter_by(test_session_id=session.id).delete()
        _save_shots(session.id, request.form)

        db.session.commit()
        flash("Test session updated.", "success")
        return redirect(url_for("test_sessions.view", id=session.id))
    return render_template(
        "test_sessions/form.html",
        session=session,
        firearms=firearms,
        loads=loads,
    )


@bp.route("/delete/<string:id>", methods=["POST"])
def delete(id):
    session = TestSession.query.get_or_404(id)
    Shot.query.filter_by(test_session_id=session.id).delete()
    db.session.delete(session)
    db.session.commit()
    flash("Test session deleted.", "success")
    return redirect(url_for("test_sessions.index"))


@bp.route("/add-shot/<string:session_id>", methods=["POST"])
def add_shot(session_id):
    """Add a single shot to an existing session."""
    session = TestSession.query.get_or_404(session_id)
    shot_number = len(session.shots) + 1

    velocity = request.form.get("velocity", "").strip()
    if not velocity:
        flash("Velocity is required.", "danger")
        return redirect(url_for("test_sessions.view", id=session_id))

    try:
        velocity_val = round(float(velocity), 2)
    except ValueError:
        flash("Velocity must be a number.", "danger")
        return redirect(url_for("test_sessions.view", id=session_id))

    shot = Shot(
        test_session_id=session_id,
        shot_number=shot_number,
        velocity=velocity_val,
        timestamp=request.form.get("timestamp", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None,
    )

    # Calculate deviation, KE, power factor after adding
    db.session.add(shot)
    db.session.flush()

    _recalculate_shot_stats(session)
    db.session.commit()

    flash(f"Shot #{shot_number} added.", "success")
    return redirect(url_for("test_sessions.view", id=session_id))


@bp.route("/delete-shot/<string:shot_id>", methods=["POST"])
def delete_shot(shot_id):
    """Delete a single shot from a session."""
    shot = Shot.query.get_or_404(shot_id)
    session_id = shot.test_session_id
    db.session.delete(shot)
    db.session.flush()

    # Renumber remaining shots and recalculate
    session = TestSession.query.get(session_id)
    for i, s in enumerate(
        Shot.query.filter_by(test_session_id=session_id)
        .order_by(Shot.shot_number)
        .all(),
        1,
    ):
        s.shot_number = i

    _recalculate_shot_stats(session)
    db.session.commit()

    flash("Shot deleted.", "success")
    return redirect(url_for("test_sessions.view", id=session_id))


def _get_session_form_data():
    """Extract and validate test session form data."""
    test_date_str = request.form.get("test_date", "").strip()
    if not test_date_str:
        flash("Test date is required.", "danger")
        return None

    try:
        test_date = datetime.strptime(test_date_str, "%Y-%m-%dT%H:%M")
    except ValueError:
        try:
            test_date = datetime.strptime(test_date_str, "%Y-%m-%d")
        except ValueError:
            flash("Invalid date format.", "danger")
            return None

    data = {"test_date": test_date}

    firearm_id = request.form.get("firearm_id", "").strip()
    data["firearm_id"] = firearm_id if firearm_id else None

    load_id = request.form.get("load_id", "").strip()
    data["load_id"] = load_id if load_id else None

    data["location"] = request.form.get("location", "").strip() or None
    data["notes"] = request.form.get("notes", "").strip() or None

    temperature = request.form.get("temperature", "").strip()
    humidity = request.form.get("humidity", "").strip()
    pressure = request.form.get("pressure", "").strip()

    temp_val = None
    humid_val = None
    press_val = None

    if temperature:
        try:
            temp_val = float(temperature)
            data["temperature"] = temp_val
        except ValueError:
            flash("Temperature must be a number.", "danger")
            return None
    else:
        data["temperature"] = None

    if humidity:
        try:
            humid_val = float(humidity)
            data["humidity"] = humid_val
        except ValueError:
            flash("Humidity must be a number.", "danger")
            return None
    else:
        data["humidity"] = None

    if pressure:
        try:
            press_val = float(pressure)
            data["pressure"] = press_val
        except ValueError:
            flash("Pressure must be a number.", "danger")
            return None
    else:
        data["pressure"] = None

    # Calculate density altitude
    da = calculate_density_altitude(temp_val, humid_val, press_val)
    data["density_altitude"] = da

    range_distance = request.form.get("range_distance", "").strip()
    if range_distance:
        try:
            data["range_distance"] = float(range_distance)
        except ValueError:
            flash("Range distance must be a number.", "danger")
            return None
    else:
        data["range_distance"] = None

    grouping_size = request.form.get("grouping_size", "").strip()
    if grouping_size:
        try:
            data["grouping_size"] = round(float(grouping_size), 4)
        except ValueError:
            flash("Grouping size must be a number.", "danger")
            return None
    else:
        data["grouping_size"] = None

    return data


def _save_shots(session_id, form):
    """Save shots from form data."""
    shot_index = 0
    while True:
        velocity_key = f"shots-{shot_index}-velocity"
        if velocity_key not in form:
            break
        velocity = form.get(velocity_key, "").strip()
        if not velocity:
            shot_index += 1
            continue
        try:
            velocity_val = round(float(velocity), 2)
        except ValueError:
            shot_index += 1
            continue

        timestamp = form.get(f"shots-{shot_index}-timestamp", "").strip()
        ke = form.get(f"shots-{shot_index}-kinetic_energy", "").strip()
        pf = form.get(f"shots-{shot_index}-power_factor", "").strip()
        notes = form.get(f"shots-{shot_index}-notes", "").strip()
        trace_data = form.get(f"shots-{shot_index}-trace_data", "").strip()

        shot = Shot(
            test_session_id=session_id,
            shot_number=shot_index + 1,
            velocity=velocity_val,
            timestamp=timestamp or None,
            kinetic_energy=float(ke) if ke else None,
            power_factor=float(pf) if pf else None,
            notes=notes or None,
            trace_data=trace_data or None,
        )
        db.session.add(shot)
        shot_index += 1

    # Recalculate deviations
    db.session.flush()
    session = TestSession.query.get(session_id)
    _recalculate_shot_stats(session)


def _recalculate_shot_stats(session):
    """Recalculate deviation for all shots in a session."""
    if not session.shots:
        return
    velocities = [s.velocity for s in session.shots if s.velocity is not None]
    if not velocities:
        return
    avg = sum(velocities) / len(velocities)
    for shot in session.shots:
        if shot.velocity is not None:
            shot.deviation = round(shot.velocity - avg, 2)

