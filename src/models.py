"""SQLAlchemy models for the reloading tracker application."""

import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def generate_uuid():
    return str(uuid.uuid4())


class Caliber(db.Model):
    __tablename__ = "calibers"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Caliber {self.name}>"


class PrimerType(db.Model):
    __tablename__ = "primer_types"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<PrimerType {self.name}>"


class Manufacturer(db.Model):
    __tablename__ = "manufacturers"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"<Manufacturer {self.name}>"


class Primer(db.Model):
    __tablename__ = "primers"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    manufacturer_id = db.Column(
        db.String(36), db.ForeignKey("manufacturers.id"), nullable=False
    )
    model = db.Column(db.String(100), nullable=False)
    primer_type_id = db.Column(
        db.Integer, db.ForeignKey("primer_types.id"), nullable=False
    )

    manufacturer = db.relationship("Manufacturer", backref="primers")
    primer_type = db.relationship("PrimerType", backref="primers")

    def __repr__(self):
        return f"<Primer {self.manufacturer.name} {self.model}>"


class Bullet(db.Model):
    __tablename__ = "bullets"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    manufacturer_id = db.Column(
        db.String(36), db.ForeignKey("manufacturers.id"), nullable=False
    )
    model = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, nullable=False)  # grains, 2 decimal places
    overall_length = db.Column(db.Float, nullable=True)  # inches, 4 decimal places
    caliber_id = db.Column(db.Integer, db.ForeignKey("calibers.id"), nullable=False)
    g7_bc = db.Column(db.Float, nullable=True)  # G7 ballistic coefficient
    g1_bc = db.Column(db.Float, nullable=True)  # G1 ballistic coefficient

    manufacturer = db.relationship("Manufacturer", backref="bullets")
    caliber = db.relationship("Caliber", backref="bullets")

    def __repr__(self):
        return f"<Bullet {self.manufacturer.name} {self.model} {self.weight}gr>"


class Casing(db.Model):
    __tablename__ = "casings"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False)
    max_trim_length = db.Column(db.Float, nullable=True)  # inches, 4 decimal places
    overall_length = db.Column(db.Float, nullable=True)  # inches, 4 decimal places
    primer_type_id = db.Column(
        db.Integer, db.ForeignKey("primer_types.id"), nullable=False
    )

    primer_type = db.relationship("PrimerType", backref="casings")

    def __repr__(self):
        return f"<Casing {self.name}>"


class Powder(db.Model):
    __tablename__ = "powders"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    manufacturer_id = db.Column(
        db.String(36), db.ForeignKey("manufacturers.id"), nullable=False
    )
    name = db.Column(db.String(100), nullable=False)

    manufacturer = db.relationship("Manufacturer", backref="powders")

    def __repr__(self):
        return f"<Powder {self.manufacturer.name} {self.name}>"


class OrderLot(db.Model):
    __tablename__ = "order_lots"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    order_date = db.Column(db.DateTime, nullable=False)
    store = db.Column(db.String(200), nullable=True)
    lot_number = db.Column(db.String(100), nullable=True)
    total_cost = db.Column(db.Float, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    is_depleted = db.Column(db.Boolean, nullable=False, default=False)
    # Polymorphic component reference
    component_type = db.Column(
        db.String(20), nullable=False
    )  # 'bullet', 'powder', 'primer', 'casing'
    bullet_id = db.Column(db.String(36), db.ForeignKey("bullets.id"), nullable=True)
    powder_id = db.Column(db.String(36), db.ForeignKey("powders.id"), nullable=True)
    primer_id = db.Column(db.String(36), db.ForeignKey("primers.id"), nullable=True)
    casing_id = db.Column(db.String(36), db.ForeignKey("casings.id"), nullable=True)

    bullet = db.relationship("Bullet", backref="order_lots")
    powder = db.relationship("Powder", backref="order_lots")
    primer = db.relationship("Primer", backref="order_lots")
    casing = db.relationship("Casing", backref="order_lots")

    @property
    def component(self):
        if self.component_type == "bullet":
            return self.bullet
        elif self.component_type == "powder":
            return self.powder
        elif self.component_type == "primer":
            return self.primer
        elif self.component_type == "casing":
            return self.casing
        return None

    # Grains per pound constant for powder cost calculation
    GRAINS_PER_POUND = 7000

    @property
    def cost_per_unit(self):
        """Cost per individual unit (per bullet, per primer, per casing, per grain for powder).

        For powder, quantity is in pounds so this returns cost per grain.
        For all other components, returns cost per individual item.
        Returns None if cost or quantity data is missing.
        """
        if self.total_cost is None or not self.quantity:
            return None
        if self.component_type == "powder":
            total_grains = self.quantity * self.GRAINS_PER_POUND
            return self.total_cost / total_grains
        return self.total_cost / self.quantity

    @property
    def component_display(self):
        comp = self.component
        if comp is None:
            return "N/A"
        if self.component_type == "bullet":
            return f"{comp.manufacturer.name} {comp.model} ({comp.weight}gr)"
        elif self.component_type == "powder":
            return f"{comp.manufacturer.name} {comp.name}"
        elif self.component_type == "primer":
            return f"{comp.manufacturer.name} {comp.model}"
        elif self.component_type == "casing":
            return f"{comp.name}"
        return "N/A"

    def __repr__(self):
        return f"<OrderLot {self.id} {self.component_type}>"


class Load(db.Model):
    __tablename__ = "loads"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    bullet_lot_id = db.Column(
        db.String(36), db.ForeignKey("order_lots.id"), nullable=True
    )
    powder_lot_id = db.Column(
        db.String(36), db.ForeignKey("order_lots.id"), nullable=True
    )
    powder_weight = db.Column(db.Float, nullable=True)  # grains, 2 decimal places
    primer_lot_id = db.Column(
        db.String(36), db.ForeignKey("order_lots.id"), nullable=True
    )
    casing_lot_id = db.Column(
        db.String(36), db.ForeignKey("order_lots.id"), nullable=True
    )
    notes = db.Column(db.Text, nullable=True)
    overall_length = db.Column(db.Float, nullable=True)  # inches, 4 decimal places
    cbto = db.Column(db.Float, nullable=True)  # inches, 4 decimal places
    date_created = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    bullet_lot = db.relationship(
        "OrderLot", foreign_keys=[bullet_lot_id], backref="bullet_loads"
    )
    powder_lot = db.relationship(
        "OrderLot", foreign_keys=[powder_lot_id], backref="powder_loads"
    )
    primer_lot = db.relationship(
        "OrderLot", foreign_keys=[primer_lot_id], backref="primer_loads"
    )
    casing_lot = db.relationship(
        "OrderLot", foreign_keys=[casing_lot_id], backref="casing_loads"
    )

    @property
    def cost_breakdown(self):
        """Calculate per-component cost for a single round.

        Returns a dict with keys: bullet, powder, primer, casing, total.
        Powder cost = cost_per_grain * powder_weight.
        All other components = cost_per_unit from their order lot.
        Values are None when data is insufficient to calculate.
        """
        costs = {}

        # Bullet cost per round
        costs["bullet"] = self.bullet_lot.cost_per_unit if self.bullet_lot else None

        # Powder cost per round: cost_per_grain * powder_weight
        if self.powder_lot and self.powder_lot.cost_per_unit is not None and self.powder_weight:
            costs["powder"] = self.powder_lot.cost_per_unit * self.powder_weight
        else:
            costs["powder"] = None

        # Primer cost per round
        costs["primer"] = self.primer_lot.cost_per_unit if self.primer_lot else None

        # Casing cost per round
        costs["casing"] = self.casing_lot.cost_per_unit if self.casing_lot else None

        # Total cost per round (sum of available components)
        known = [v for v in costs.values() if v is not None]
        costs["total"] = sum(known) if known else None

        return costs

    @property
    def cost_per_round(self):
        """Estimated total cost per round based on order lot prices."""
        return self.cost_breakdown["total"]

    def __repr__(self):
        return f"<Load {self.id}>"


class Firearm(db.Model):
    __tablename__ = "firearms"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    make = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    caliber_id = db.Column(db.Integer, db.ForeignKey("calibers.id"), nullable=False)
    barrel_length = db.Column(db.Float, nullable=True)  # inches
    twist_rate = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    caliber = db.relationship("Caliber", backref="firearms")

    def __repr__(self):
        return f"<Firearm {self.make} {self.model}>"


class TestSession(db.Model):
    __tablename__ = "test_sessions"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    firearm_id = db.Column(
        db.String(36), db.ForeignKey("firearms.id"), nullable=True
    )
    test_date = db.Column(db.DateTime, nullable=False)
    load_id = db.Column(db.String(36), db.ForeignKey("loads.id"), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    temperature = db.Column(db.Float, nullable=True)  # Fahrenheit
    humidity = db.Column(db.Float, nullable=True)  # percentage
    pressure = db.Column(db.Float, nullable=True)  # inches of mercury
    density_altitude = db.Column(db.Float, nullable=True)  # feet
    notes = db.Column(db.Text, nullable=True)
    range_distance = db.Column(db.Float, nullable=True)  # yards
    grouping_size = db.Column(db.Float, nullable=True)  # MOA, 4 decimal places

    firearm = db.relationship("Firearm", backref="test_sessions")
    load = db.relationship("Load", backref="test_sessions")

    @property
    def shot_count(self):
        return len(self.shots)

    @property
    def velocity_avg(self):
        if not self.shots:
            return None
        velocities = [s.velocity for s in self.shots if s.velocity is not None]
        if not velocities:
            return None
        return round(sum(velocities) / len(velocities), 2)

    @property
    def standard_deviation(self):
        if not self.shots or len(self.shots) < 2:
            return None
        velocities = [s.velocity for s in self.shots if s.velocity is not None]
        if len(velocities) < 2:
            return None
        avg = sum(velocities) / len(velocities)
        variance = sum((v - avg) ** 2 for v in velocities) / (len(velocities) - 1)
        return round(variance**0.5, 2)

    @property
    def extreme_spread(self):
        if not self.shots:
            return None
        velocities = [s.velocity for s in self.shots if s.velocity is not None]
        if not velocities:
            return None
        return round(max(velocities) - min(velocities), 2)

    def __repr__(self):
        return f"<TestSession {self.id}>"


class Shot(db.Model):
    __tablename__ = "shots"
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    test_session_id = db.Column(
        db.String(36), db.ForeignKey("test_sessions.id"), nullable=False
    )
    shot_number = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.String(50), nullable=True)
    velocity = db.Column(db.Float, nullable=True)  # fps, 2 decimal places
    deviation = db.Column(db.Float, nullable=True)  # fps
    kinetic_energy = db.Column(db.Float, nullable=True)  # ft/lbs
    power_factor = db.Column(db.Float, nullable=True)
    trace_data = db.Column(db.Text, nullable=True)  # JSON string
    notes = db.Column(db.Text, nullable=True)

    test_session = db.relationship(
        "TestSession", backref=db.backref("shots", order_by="Shot.shot_number")
    )

    def __repr__(self):
        return f"<Shot {self.shot_number} @ {self.velocity}fps>"

