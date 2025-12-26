import os, json, pandas as pd, plotly, plotly.express as px
from doctest import TestResults

from flask import Flask, render_template, request, redirect, url_for, flash
from database import db, Firearm, Bullet, Powder, Cartridge, Load, TestSession, TestResult, Shot
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'reloading_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db.init_app(app)

@app.route('/')
def index():
    # Filtering Logic
    f_id = request.args.get('f_id')
    b_id = request.args.get('b_id')
    p_id = request.args.get('p_id')

    full_bullet_name = func.concat(Bullet.manufacturer, ' ', Bullet.model)
    full_firearm_name = func.concat(Firearm.make, ' ', Firearm.model)
    full_powder_name = func.concat(Powder.manufacturer, ' ', Powder.name)

    query = (
        db.session.query(
            Shot.velocity_fps,
            Load.powder_weight_grains,
            full_firearm_name.label('firearm_name'),
            full_bullet_name.label('bullet_name')
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
    
    # DEBUG: Print this to your console to see if any rows were found
    print(f"DEBUG: Found {len(df)} rows for the chart.")
    if not df.empty:
        print(df.head()) # See the first few rows

    chart_json = None
    if not df.empty:
        fig = px.scatter(
            df,
            x="powder_weight_grains",
            y="velocity_fps",
            color="firearm_name",
            hover_data=['bullet_name'],
            title="Charge Weight vs Velocity",
            labels={"powder_weight_grains": "Powder Charge (gr)", "velocity_fps": "Velocity (fps)"},
            template="plotly_white"
        )
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    firearms = Firearm.query.all()
    bullets = Bullet.query.all()
    powders = Powder.query.all()
    sessions = TestSession.query.order_by(TestSession.test_date.desc()).all()
    results = (
        db.session.query(
            full_firearm_name.label('firearm_name'),
            TestSession.test_date,
            TestSession.session_id,
            TestSession.temperature_f,
            TestSession.location,
            full_bullet_name.label('bullet_name'),
            full_powder_name.label('powder_name'),
        )
        .select_from(TestResult)
        .join(TestSession, TestResult.session_id == TestSession.session_id)
        .join(Firearm, TestSession.firearm_id == Firearm.firearm_id)
        .join(Load, TestResult.load_id == Load.load_id)
        .join(Bullet, Load.bullet_id == Bullet.bullet_id)
        .all()
    )

    return render_template('index.html',
                           chart_json=chart_json,
                           firearms=firearms,
                           bullets=bullets,
                           powders=powders,
                           results=results)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True)