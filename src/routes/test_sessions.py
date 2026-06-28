"""Routes for managing test sessions and shots."""

import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, TestSession, Shot, Firearm, Load, OrderLot
from utils.calculations import calculate_density_altitude

bp = Blueprint("test_sessions", __name__, url_prefix="/test-sessions")


@bp.route("/")
def index():
    firearm_id = request.args.get("firearm_id", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    location = request.args.get("location", "").strip()

    query = TestSession.query

    if firearm_id:
        query = query.filter(TestSession.firearm_id == firearm_id)

    if date_from:
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(TestSession.test_date >= start_date)
        except ValueError:
            flash("Invalid start date filter.", "danger")

    if date_to:
        try:
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            query = query.filter(TestSession.test_date < end_date.replace(hour=23, minute=59, second=59, microsecond=999999))
        except ValueError:
            flash("Invalid end date filter.", "danger")

    if location:
        query = query.filter(TestSession.location == location)

    sort = request.args.get("sort", "date").strip()
    sort_dir = request.args.get("sort_dir", "desc").strip()
    if sort_dir not in ("asc", "desc"):
        sort_dir = "desc"

    sort_map = {
        "date": TestSession.test_date,
        "location": TestSession.location,
        "grouping_size": TestSession.grouping_size,
    }
    if sort in sort_map:
        order_col = sort_map[sort]
        if sort_dir == "asc":
            query = query.order_by(db.asc(order_col))
        else:
            query = query.order_by(db.desc(order_col))
        sessions = query.all()
    else:
        sort = "date"
        query = query.order_by(db.desc(TestSession.test_date))
        sessions = query.all()

    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    locations = (
        db.session.query(TestSession.location)
        .filter(TestSession.location.isnot(None), TestSession.location != "")
        .distinct()
        .order_by(TestSession.location)
        .all()
    )
    location_list = [item[0] for item in locations]

    return render_template(
        "test_sessions/index.html",
        sessions=sessions,
        firearms=firearms,
        location_list=location_list,
        current_filters={
            "firearm_id": firearm_id,
            "date_from": date_from,
            "date_to": date_to,
            "location": location,
        },
        current_sort=sort,
        current_sort_dir=sort_dir,
    )


@bp.route("/view/<string:id>")
def view(id):
    session = TestSession.query.get_or_404(id)
    view_mode = request.args.get("view", "full").strip()
    session_view = _build_session_view(session, view_mode)
    return render_template(
        "test_sessions/view.html",
        session=session,
        session_view=session_view,
    )


@bp.route("/add", methods=["GET", "POST"])
def add():
    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    loads = Load.query.order_by(Load.date_created.desc()).all()
    factory_ammo_lots = _get_factory_ammo_lot_choices()
    if request.method == "POST":
        data = _get_session_form_data()
        if data is None:
            return render_template(
                "test_sessions/form.html",
                session=None,
                firearms=firearms,
                loads=loads,
                factory_ammo_lots=factory_ammo_lots,
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
        factory_ammo_lots=factory_ammo_lots,
    )


@bp.route("/edit/<string:id>", methods=["GET", "POST"])
def edit(id):
    session = TestSession.query.get_or_404(id)
    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    loads = Load.query.order_by(Load.date_created.desc()).all()
    factory_ammo_lots = _get_factory_ammo_lot_choices()
    if request.method == "POST":
        data = _get_session_form_data()
        if data is None:
            return render_template(
                "test_sessions/form.html",
                session=session,
                firearms=firearms,
                loads=loads,
                factory_ammo_lots=factory_ammo_lots,
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
        factory_ammo_lots=factory_ammo_lots,
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

    timestamp = _format_timestamp(
        request.form.get("timestamp", "").strip()
    )

    shot = Shot(
        test_session_id=session_id,
        shot_number=shot_number,
        velocity=velocity_val,
        timestamp=timestamp or None,
        notes=request.form.get("notes", "").strip() or None,
    )

    # Calculate deviation, KE, power factor after adding
    db.session.add(shot)
    db.session.flush()

    # Expire cached shots collection so it includes the new shot
    db.session.expire(session, ["shots"])
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


def _get_factory_ammo_lot_choices():
    return (
        OrderLot.query.filter_by(component_type="factory_ammo")
        .order_by(OrderLot.order_date.desc())
        .all()
    )


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
    factory_ammo_lot_id = request.form.get("factory_ammo_lot_id", "").strip()

    if load_id and factory_ammo_lot_id:
        flash("Select either a load/recipe or a factory ammo order lot, not both.", "danger")
        return None

    data["load_id"] = load_id if load_id else None
    data["factory_ammo_lot_id"] = (
        factory_ammo_lot_id if factory_ammo_lot_id else None
    )

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


def _format_timestamp(value):
    """Format a timestamp string ensuring uppercase AM/PM with a single space.

    Examples: '10:30am' -> '10:30 AM', '2:15 pm' -> '2:15 PM',
              '10:30  AM' -> '10:30 AM'
    """
    if not value:
        return value
    import re
    # Match optional time portion followed by am/pm with optional spacing
    formatted = re.sub(
        r'\s*(am|pm)\s*$',
        lambda m: ' ' + m.group(1).upper(),
        value.strip(),
        flags=re.IGNORECASE,
    )
    return formatted


def _get_bullet_weight(session):
    """Get bullet weight in grains from the session ammo source, if available."""
    if session.load and session.load.bullet_lot and session.load.bullet_lot.bullet:
        return session.load.bullet_lot.bullet.weight
    if (
        session.factory_ammo_lot
        and session.factory_ammo_lot.factory_ammo
        and session.factory_ammo_lot.factory_ammo.weight
    ):
        return session.factory_ammo_lot.factory_ammo.weight


def _calculate_velocity_metrics(shots):
    """Calculate aggregate shot metrics for a session view."""
    velocities = [shot.velocity for shot in shots if shot.velocity is not None]
    if not velocities:
        return {
            "shot_count": len(shots),
            "velocity_avg": None,
            "standard_deviation": None,
            "velocity_min": None,
            "velocity_max": None,
            "extreme_spread": None,
        }

    avg = sum(velocities) / len(velocities)
    variance = None
    if len(velocities) >= 2:
        variance = sum((velocity - avg) ** 2 for velocity in velocities) / len(velocities)

    return {
        "shot_count": len(shots),
        "velocity_avg": round(avg, 2),
        "standard_deviation": round(variance**0.5, 2) if variance is not None else None,
        "velocity_min": round(min(velocities), 2),
        "velocity_max": round(max(velocities), 2),
        "extreme_spread": round(max(velocities) - min(velocities), 2),
    }


def _get_excluded_shot_ids(shots):
    """Return the slowest and fastest shot ids to exclude from calculations."""
    velocity_shots = [shot for shot in shots if shot.velocity is not None]
    if len(velocity_shots) < 2:
        return set()

    sorted_shots = sorted(velocity_shots, key=lambda shot: (shot.velocity, shot.shot_number))
    return {sorted_shots[0].id, sorted_shots[-1].id}


def _build_metric_deltas(current_metrics, full_metrics):
    """Build metric deltas between the current and full session views."""
    precision_map = {
        "shot_count": 0,
        "velocity_avg": 2,
        "standard_deviation": 2,
        "velocity_min": 2,
        "velocity_max": 2,
        "extreme_spread": 2,
    }
    deltas = {}
    for key, precision in precision_map.items():
        current_value = current_metrics.get(key)
        full_value = full_metrics.get(key)
        if current_value is None or full_value is None:
            deltas[key] = None
            continue
        delta = current_value - full_value
        deltas[key] = int(delta) if precision == 0 else round(delta, precision)
    return deltas


def _build_session_view(session, view_mode):
    """Build the display model for the full or excluded-shot session view."""
    shots = list(session.shots)
    can_exclude = len(shots) > 5
    is_excluded_mode = view_mode == "excluded" and can_exclude
    excluded_shot_ids = _get_excluded_shot_ids(shots) if is_excluded_mode else set()
    included_shots = [shot for shot in shots if shot.id not in excluded_shot_ids]

    full_metrics = _calculate_velocity_metrics(shots)
    current_metrics = (
        _calculate_velocity_metrics(included_shots)
        if is_excluded_mode
        else dict(full_metrics)
    )
    current_metrics["grouping_size"] = session.grouping_size
    current_metrics["range_distance"] = session.range_distance
    full_metrics["grouping_size"] = session.grouping_size
    full_metrics["range_distance"] = session.range_distance

    current_avg = current_metrics.get("velocity_avg")
    shot_rows = []
    excluded_shot_numbers = []
    for shot in shots:
        is_excluded = shot.id in excluded_shot_ids
        if is_excluded:
            excluded_shot_numbers.append(shot.shot_number)
        deviation = None
        if shot.velocity is not None and current_avg is not None and not is_excluded:
            deviation = round(shot.velocity - current_avg, 2)
        shot_rows.append(
            {
                "shot": shot,
                "is_excluded": is_excluded,
                "deviation": deviation,
            }
        )

    return {
        "mode": "excluded" if is_excluded_mode else "full",
        "is_excluded_mode": is_excluded_mode,
        "can_exclude": can_exclude,
        "shots": shot_rows,
        "metrics": current_metrics,
        "full_metrics": full_metrics,
        "deltas": _build_metric_deltas(current_metrics, full_metrics),
        "excluded_shot_numbers": excluded_shot_numbers,
    }

    return None


def _recalculate_shot_stats(session):
    """Recalculate deviation, kinetic energy, and power factor for all shots."""
    if not session.shots:
        return
    velocities = [s.velocity for s in session.shots if s.velocity is not None]
    if not velocities:
        return
    avg = sum(velocities) / len(velocities)
    bullet_weight = _get_bullet_weight(session)

    for shot in session.shots:
        if shot.velocity is not None:
            shot.deviation = round(shot.velocity - avg, 2)
            # Auto-calculate KE and Power Factor if not already set
            if bullet_weight and shot.kinetic_energy is None:
                shot.kinetic_energy = round(
                    (bullet_weight * shot.velocity ** 2) / 450240, 2
                )
            if bullet_weight and shot.power_factor is None:
                shot.power_factor = round(
                    (bullet_weight * shot.velocity) / 1000, 2
                )

