import os, json, pandas as pd, plotly, plotly.express as px

from decimal import Decimal
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

# --- FIREARM LIST ---
@app.route('/firearms')
def list_firearms():
    firearms = Firearm.query.all()
    return render_template('firearms/list.html', firearms=firearms)

# --- ADD FIREARM ---
@app.route('/firearms/add', methods=['GET', 'POST'])
def add_firearm():
    if request.method == 'POST':
        new_f = Firearm(
            make=request.form['make'],
            model=request.form['model'],
            caliber=request.form['caliber'],
            barrel_length=request.form['barrel_length'],
            twist_rate=request.form['twist_rate'],
            notes=request.form['notes']
        )
        db.session.add(new_f)
        db.session.commit()
        flash('Firearm added successfully!')
        return redirect(url_for('list_firearms'))
    return render_template('firearms/form.html', firearm=None)

# --- EDIT FIREARM ---
@app.route('/firearms/edit/<int:fid>', methods=['GET', 'POST'])
def edit_firearm(fid):
    f = Firearm.query.get_or_404(fid)
    if request.method == 'POST':
        f.name = request.form['name']
        f.model = request.form['model']
        f.caliber = request.form['caliber']
        f.barrel_length = request.form['barrel_length']
        f.twist_rate = request.form['twist_rate']
        f.notes = request.form['notes']
        db.session.commit()
        return redirect(url_for('list_firearms'))
    return render_template('firearms/form.html', firearm=f)


# --- DELETE FIREARM ---
@app.route('/firearms/delete/<int:fid>', methods=['POST'])
def delete_firearm(fid):
#    f = Firearm.query.get_or_404(fid)
#    db.session.delete(f)
#    db.session.commit()
    flash('Firearm removed.' + fid)
    return redirect(url_for('list_firearms'))


# --- FIREARM DETAILS & ANALYTICS ---
@app.route('/firearm/<int:fid>')
def firearm_detail(fid):
    f = Firearm.query.get_or_404(fid)

    full_bullet_name = func.concat(Bullet.manufacturer, ' ', Bullet.model)
    full_powder_name = func.concat(Powder.manufacturer, ' ', Powder.name)

    # 1. Fetch Sessions for this Firearm
    sessions = TestSession.query.filter_by(firearm_id=fid).order_by(TestSession.test_date.desc()).all()

    # 2. Analytics Query: Get all shots associated with this firearm
    query = (
        db.session.query(
            Shot.velocity_fps,
            Load.powder_weight_grains,
            TestResult.group_size_moa,
            full_bullet_name.label('bullet_name'),
            full_powder_name.label('powder_name'),
            (full_bullet_name + "<br>" + full_powder_name).label('full_name')
        )
        .select_from(TestResult)
        .join(TestSession, TestResult.session_id == TestSession.session_id)
        .join(Firearm, TestSession.firearm_id == Firearm.firearm_id)
        .join(Load, TestResult.load_id == Load.load_id)
        .join(Bullet, Load.bullet_id == Bullet.bullet_id)
        .filter(Firearm.firearm_id == fid)
    )

    df = pd.read_sql(query.statement, db.engine)

    chart_json = None
    summary = {"best_moa": "N/A", "avg_fps": "N/A", "total_shots": 0}

    if not df.empty:
        # Summary stats
        summary["best_moa"] = df['group_size_moa'].min()
        summary["avg_fps"] = round(df['velocity_fps'].mean(), 1)
        summary["total_shots"] = len(df)

        # Graph: Velocity Ladder for this specific rifle
        fig = px.scatter(
            df, x="powder_weight_grains", y="velocity_fps", color="full_name",
            title=f"Load Performance: {f.make} {f.model}",
            labels={"powder_weight_grains": "Charge (gr)", "velocity_fps": "Velocity (fps)", "full_name": "Load Name"},
            template="plotly_white", trendline="lowess"
        )
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template('firearms/detail.html', firearm=f, sessions=sessions, chart_json=chart_json, summary=summary)


def format_numeric_caliber(val):
    if val is None:
        return ""
    
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
        
    normalized_val = val.quantize(Decimal('0.000'))
    
    diameter_map = {
        Decimal('0.223'): "5.56mm",
        Decimal('0.224'): "5.56mm",
        Decimal('0.243'): "6mm",
        Decimal('0.264'): "6.5mm",
        Decimal('0.277'): "6.8mm",
        Decimal('0.284'): "7mm",
        Decimal('0.308'): "7.62mm",
        Decimal('0.311'): "7.62mm Rus",
        Decimal('0.355'): "9mm",
        Decimal('0.356'): "9mm",
        Decimal('0.357'): "9mm / .38 cal",
        Decimal('0.400'): "10mm",
        Decimal('0.500'): "12.7mm"
    }

    formatted_str = f"{normalized_val:f}".lstrip('0')

    if not formatted_str or formatted_str.startswith(''):
        if not formatted_str.startswith('.'):
            formatted_str = f"0{formatted_str}" if formatted_str else "0"

    metric = diameter_map.get(normalized_val)

    return f"{formatted_str} ({metric})" if metric else formatted_str

app.jinja_env.filters['display_caliber'] = format_numeric_caliber
    
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True)