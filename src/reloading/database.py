from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class Firearm(db.Model):
    __tablename__ = 'firearms'
    firearm_id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(100))
    model = db.Column(db.String(100))
    caliber = db.Column(db.Numeric(4,3))
    barrel_length = db.Column(db.Numeric(4,2))
    twist_rate = db.Column(db.String(20))
    notes = db.Column(db.Text)

class Bullet(db.Model):
    __tablename__ = 'bullets'
    bullet_id = db.Column(db.Integer, primary_key=True)
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    weight_grains = db.Column(db.Numeric(6,2))
    overall_length_inch = db.Column(db.Numeric(4,3))
    caliber = db.Column(db.Numeric(4,3))
    ballistic_coefficient_g7 = db.Column(db.Numeric(5,4))
    ballistic_coefficient_g1 = db.Column(db.Numeric(5,4))

class Powder(db.Model):
    __tablename__ = 'powders'
    powder_id = db.Column(db.Integer, primary_key=True)
    manufacturer = db.Column(db.String(100))
    name = db.Column(db.String(100))

class Cartridge(db.Model):
    __tablename__ = 'cartridges'
    cartridge_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class Load(db.Model):
    __tablename__ = 'loads'
    load_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    cartridge_id = db.Column(db.Integer, db.ForeignKey('cartridge.id'))
    bullet_id = db.Column(db.Integer, db.ForeignKey('bullet.id'))
    powder_id = db.Column(db.Integer, db.ForeignKey('powder.id'))
    powder_weight_grains = db.Column(db.Float)
    primer_details = db.column(db.String(100))
    case_details = db.column(db.String(100))
    overall_length_inches = db.Column(db.Float)
    base_to_ogive_inch = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    notes = db.Column(db.Text)

class TestSession(db.Model):
    __tablename__ = 'test_sessions'
    session_id = db.Column(db.Integer, primary_key=True)
    firearm_id = db.Column(db.Integer, db.ForeignKey('firearm.id'))
    test_date = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    temperature_f = db.Column(db.Integer)
    density_altitude_ft = db.Column(db.Integer)
    humidity_percent = db.Column(db.Integer)
    notes = db.Column(db.Text)

class TestResult(db.Model):
    __tablename__ = 'test_results'
    result_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('test_sessions.session_id'))
    load_id = db.Column(db.Integer, db.ForeignKey('loads.load_id'))
    range_yrd = db.Column(db.Integer)
    group_size_moa = db.Column(db.Numeric(5,3))
    muzzle_velocity_avg = db.Column(db.Numeric(7,2))
    standard_deviation = db.Column(db.Numeric(5,2))
    extreme_spread = db.Column(db.Numeric(5,2))
    shot_count = db.Column(db.Integer)
    notes = db.Column(db.Text)
    max = db.Column(db.Numeric(7,2))
    min = db.Column(db.Numeric(7,2))

class Shot(db.Model):
    __tablename__ = 'shots'
    shot_id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('test_results.result_id'))
    shot_number = db.Column(db.Integer)
    velocity_fps = db.Column(db.Numeric(7,2))
    trace_data = db.Column(JSONB)
