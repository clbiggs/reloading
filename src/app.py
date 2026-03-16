"""Main Flask application for the Reloading Tracker."""

import os
from flask import Flask, render_template
from models import db, TestSession, Firearm, Load, Bullet, Powder
from database import init_db


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "reloading-tracker-secret-key-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB upload limit

    # Initialize database
    init_db(app)

    # Register blueprints
    from routes import (
        calibers,
        primer_types,
        manufacturers,
        primers,
        bullets,
        casings,
        powders,
        order_lots,
        loads,
        firearms,
        test_sessions,
        upload,
        summaries,
        backup,
    )

    app.register_blueprint(calibers.bp)
    app.register_blueprint(primer_types.bp)
    app.register_blueprint(manufacturers.bp)
    app.register_blueprint(primers.bp)
    app.register_blueprint(bullets.bp)
    app.register_blueprint(casings.bp)
    app.register_blueprint(powders.bp)
    app.register_blueprint(order_lots.bp)
    app.register_blueprint(loads.bp)
    app.register_blueprint(firearms.bp)
    app.register_blueprint(test_sessions.bp)
    app.register_blueprint(upload.bp)
    app.register_blueprint(summaries.bp)
    app.register_blueprint(backup.bp)

    @app.route("/")
    def index():
        recent_sessions = (
            TestSession.query.order_by(TestSession.test_date.desc()).limit(5).all()
        )
        firearm_count = Firearm.query.count()
        load_count = Load.query.count()
        session_count = TestSession.query.count()
        bullet_count = Bullet.query.count()
        powder_count = Powder.query.count()
        return render_template(
            "index.html",
            recent_sessions=recent_sessions,
            firearm_count=firearm_count,
            load_count=load_count,
            session_count=session_count,
            bullet_count=bullet_count,
            powder_count=powder_count,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)

