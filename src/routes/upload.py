"""Routes for uploading chronograph data."""

import io
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, TestSession, Shot, Firearm, Load
from utils.chronograph_parser import parse_chronograph_xlsx
from utils.calculations import calculate_density_altitude

bp = Blueprint("upload", __name__, url_prefix="/upload")


def _get_import_session_datetime(test_date_str, summary, shots_data):
    """Choose the imported session datetime.

    Preserve an explicitly supplied datetime or export summary time. If the
    chosen date has no time, use the first shot timestamp when available.
    """
    parsed_form_datetime = _parse_form_datetime(test_date_str)
    if parsed_form_datetime:
        test_date, has_time = parsed_form_datetime
        if has_time:
            return test_date
        return _with_time(test_date, _first_shot_time(shots_data)) or test_date

    summary_date = _parse_date(summary.get("date"))
    summary_time = _parse_time(summary.get("time"))
    if summary_date:
        test_date = datetime.combine(
            summary_date.date(), summary_time or datetime.min.time()
        )
        if summary_time:
            return test_date
        return _with_time(test_date, _first_shot_time(shots_data)) or test_date

    test_date = datetime.now(timezone.utc)
    return _with_time(test_date, _first_shot_time(shots_data)) or test_date


def _parse_form_datetime(value):
    if not value:
        return None

    for date_format, has_time in (("%Y-%m-%dT%H:%M", True), ("%Y-%m-%d", False)):
        try:
            return datetime.strptime(value, date_format), has_time
        except ValueError:
            continue

    return None


def _parse_date(value):
    if not value:
        return None

    for date_format in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value).strip(), date_format)
        except ValueError:
            continue

    return None


def _first_shot_time(shots_data):
    for shot_data in shots_data:
        shot_time = _parse_time(shot_data.get("timestamp"))
        if shot_time:
            return shot_time
    return None


def _parse_time(value):
    if not value:
        return None

    text = str(value).strip().upper()
    for time_format in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, time_format).time()
        except ValueError:
            continue

    return None


def _with_time(test_date, shot_time):
    if not shot_time:
        return None
    return datetime.combine(test_date.date(), shot_time, tzinfo=test_date.tzinfo)


@bp.route("/", methods=["GET", "POST"])
def index():
    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    loads = Load.query.order_by(Load.date_created.desc()).all()

    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Please select a file to upload.", "danger")
            return render_template(
                "upload/index.html", firearms=firearms, loads=loads
            )

        if not file.filename.lower().endswith(".xlsx"):
            flash("Only .xlsx files are supported.", "danger")
            return render_template(
                "upload/index.html", firearms=firearms, loads=loads
            )

        try:
            file_bytes = io.BytesIO(file.read())
            parsed = parse_chronograph_xlsx(file_bytes)
        except Exception as e:
            flash(f"Error parsing file: {str(e)}", "danger")
            return render_template(
                "upload/index.html", firearms=firearms, loads=loads
            )

        # Create test session from parsed data
        weather = parsed.get("weather", {})
        summary = parsed.get("summary", {})
        shots_data = parsed.get("shots", [])

        temp = weather.get("temperature")
        humidity = weather.get("humidity")
        pressure = weather.get("pressure")
        da = calculate_density_altitude(temp, humidity, pressure)

        # Get optional form data
        firearm_id = request.form.get("firearm_id", "").strip()
        load_id = request.form.get("load_id", "").strip()
        location = request.form.get("location", "").strip()
        test_date_str = request.form.get("test_date", "").strip()
        range_distance = request.form.get("range_distance", "").strip()
        grouping_size = request.form.get("grouping_size", "").strip()

        test_date = _get_import_session_datetime(test_date_str, summary, shots_data)

        # Build notes from summary
        notes_parts = []
        if summary.get("type"):
            notes_parts.append(f"Type: {summary['type']}")
        if summary.get("session_notes"):
            notes_parts.append(summary["session_notes"])
        user_notes = request.form.get("notes", "").strip()
        if user_notes:
            notes_parts.append(user_notes)

        session = TestSession(
            firearm_id=firearm_id if firearm_id else None,
            test_date=test_date,
            load_id=load_id if load_id else None,
            location=location or None,
            temperature=temp,
            humidity=humidity,
            pressure=pressure,
            density_altitude=da,
            notes="\n".join(notes_parts) if notes_parts else None,
            range_distance=float(range_distance) if range_distance else None,
            grouping_size=round(float(grouping_size), 4) if grouping_size else None,
        )
        db.session.add(session)
        db.session.flush()

        # Add shots
        for shot_data in shots_data:
            shot = Shot(
                test_session_id=session.id,
                shot_number=shot_data["shot_number"],
                timestamp=shot_data.get("timestamp"),
                velocity=round(shot_data["velocity"], 2)
                if shot_data.get("velocity")
                else None,
                kinetic_energy=shot_data.get("kinetic_energy"),
                power_factor=shot_data.get("power_factor"),
                trace_data=shot_data.get("trace_data"),
                notes=shot_data.get("notes"),
            )
            db.session.add(shot)

        # Recalculate imported shot statistics so deviations use full precision.
        db.session.flush()
        velocities = [
            shot.velocity for shot in session.shots if shot.velocity is not None
        ]
        if velocities:
            avg = sum(velocities) / len(velocities)
            for shot in session.shots:
                if shot.velocity is not None:
                    shot.deviation = round(shot.velocity - avg, 2)

        db.session.commit()
        flash(
            f"Chronograph data imported: {len(shots_data)} shots.", "success"
        )
        return redirect(url_for("test_sessions.view", id=session.id))

    return render_template("upload/index.html", firearms=firearms, loads=loads)

