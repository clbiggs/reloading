"""Routes for summary views."""

from flask import Blueprint, render_template, request
from models import db, Firearm, Load, Bullet, Powder, OrderLot, TestSession

bp = Blueprint("summaries", __name__, url_prefix="/summaries")


def _get_selected_sessions(sessions):
    """Return the sessions included in summary stats and charts."""
    if request.args.get("session_filter"):
        selected_ids = set(request.args.getlist("session_id"))
    else:
        selected_ids = {session.id for session in sessions}

    selected_sessions = [session for session in sessions if session.id in selected_ids]
    return selected_sessions, selected_ids


def _get_sorted_sessions(query):
    """Apply main test sessions page sort options to a summary session query."""
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
    else:
        sort = "date"
        sort_dir = "desc"
        query = query.order_by(db.desc(TestSession.test_date))

    return query.all(), sort, sort_dir


@bp.route("/")
def index():
    return render_template("summaries/index.html")


@bp.route("/by-firearm")
def by_firearm():
    """Summary of test sessions grouped by firearm."""
    firearms = Firearm.query.order_by(Firearm.make, Firearm.model).all()
    firearm_id = request.args.get("firearm_id")

    selected_firearm = None
    sessions = []
    selected_sessions = []
    selected_session_ids = set()
    stats = {}
    current_sort = "date"
    current_sort_dir = "desc"

    if firearm_id:
        selected_firearm = Firearm.query.get(firearm_id)
        if selected_firearm:
            sessions, current_sort, current_sort_dir = _get_sorted_sessions(
                TestSession.query.filter_by(firearm_id=firearm_id)
            )
            selected_sessions, selected_session_ids = _get_selected_sessions(sessions)
            stats = _calculate_session_stats(selected_sessions)

    return render_template(
        "summaries/by_firearm.html",
        firearms=firearms,
        selected_firearm=selected_firearm,
        sessions=sessions,
        selected_sessions=selected_sessions,
        selected_session_ids=selected_session_ids,
        stats=stats,
        current_sort=current_sort,
        current_sort_dir=current_sort_dir,
    )


@bp.route("/by-bullet")
def by_bullet():
    """Summary of test sessions grouped by bullet."""
    bullets = Bullet.query.join(Bullet.manufacturer).order_by(Bullet.model).all()
    bullet_id = request.args.get("bullet_id")

    selected_bullet = None
    sessions = []
    selected_sessions = []
    selected_session_ids = set()
    stats = {}
    current_sort = "date"
    current_sort_dir = "desc"

    if bullet_id:
        selected_bullet = Bullet.query.get(bullet_id)
        if selected_bullet:
            # Find sessions that use loads with order lots containing this bullet
            bullet_lot_ids = [
                lot.id
                for lot in OrderLot.query.filter_by(
                    component_type="bullet", bullet_id=bullet_id
                ).all()
            ]
            if bullet_lot_ids:
                load_ids = [
                    load.id
                    for load in Load.query.filter(
                        Load.bullet_lot_id.in_(bullet_lot_ids)
                    ).all()
                ]
                if load_ids:
                    sessions, current_sort, current_sort_dir = _get_sorted_sessions(
                        TestSession.query.filter(TestSession.load_id.in_(load_ids))
                    )
            selected_sessions, selected_session_ids = _get_selected_sessions(sessions)
            stats = _calculate_session_stats(selected_sessions)

    return render_template(
        "summaries/by_bullet.html",
        bullets=bullets,
        selected_bullet=selected_bullet,
        sessions=sessions,
        selected_sessions=selected_sessions,
        selected_session_ids=selected_session_ids,
        stats=stats,
        current_sort=current_sort,
        current_sort_dir=current_sort_dir,
    )


@bp.route("/by-powder")
def by_powder():
    """Summary of test sessions grouped by powder."""
    powders = Powder.query.join(Powder.manufacturer).order_by(Powder.name).all()
    powder_id = request.args.get("powder_id")

    selected_powder = None
    sessions = []
    selected_sessions = []
    selected_session_ids = set()
    stats = {}
    current_sort = "date"
    current_sort_dir = "desc"

    if powder_id:
        selected_powder = Powder.query.get(powder_id)
        if selected_powder:
            # Find sessions that use loads with order lots containing this powder
            powder_lot_ids = [
                lot.id
                for lot in OrderLot.query.filter_by(
                    component_type="powder", powder_id=powder_id
                ).all()
            ]
            if powder_lot_ids:
                load_ids = [
                    load.id
                    for load in Load.query.filter(
                        Load.powder_lot_id.in_(powder_lot_ids)
                    ).all()
                ]
                if load_ids:
                    sessions, current_sort, current_sort_dir = _get_sorted_sessions(
                        TestSession.query.filter(TestSession.load_id.in_(load_ids))
                    )
            selected_sessions, selected_session_ids = _get_selected_sessions(sessions)
            stats = _calculate_session_stats(selected_sessions)

    return render_template(
        "summaries/by_powder.html",
        powders=powders,
        selected_powder=selected_powder,
        sessions=sessions,
        selected_sessions=selected_sessions,
        selected_session_ids=selected_session_ids,
        stats=stats,
        current_sort=current_sort,
        current_sort_dir=current_sort_dir,
    )


def _calculate_session_stats(sessions):
    """Calculate aggregate statistics across multiple test sessions."""
    if not sessions:
        return {}

    all_velocities = []
    total_shots = 0
    session_count = len(sessions)
    best_sd = None
    best_es = None
    best_grouping = None

    for session in sessions:
        for shot in session.shots:
            if shot.velocity is not None:
                all_velocities.append(shot.velocity)
        total_shots += session.shot_count

        sd = session.standard_deviation
        if sd is not None and (best_sd is None or sd < best_sd):
            best_sd = sd

        es = session.extreme_spread
        if es is not None and (best_es is None or es < best_es):
            best_es = es

        if session.grouping_size is not None and (
            best_grouping is None or session.grouping_size < best_grouping
        ):
            best_grouping = session.grouping_size

    stats = {
        "session_count": session_count,
        "total_shots": total_shots,
        "best_sd": round(best_sd, 2) if best_sd is not None else None,
        "best_es": round(best_es, 2) if best_es is not None else None,
        "best_grouping": round(best_grouping, 4) if best_grouping is not None else None,
    }

    if all_velocities:
        stats["avg_velocity"] = round(sum(all_velocities) / len(all_velocities), 2)
        stats["min_velocity"] = round(min(all_velocities), 2)
        stats["max_velocity"] = round(max(all_velocities), 2)
        if len(all_velocities) >= 2:
            avg = sum(all_velocities) / len(all_velocities)
            variance = sum((v - avg) ** 2 for v in all_velocities) / (
                len(all_velocities) - 1
            )
            stats["overall_sd"] = round(variance**0.5, 2)

    return stats

