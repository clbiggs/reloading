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

    @property
    def usage_unit_label(self):
        """Human-readable unit label for usage charts."""
        return "grains" if self.component_type == "powder" else "units"

    @property
    def total_units(self):
        """Total usable units in the lot."""
        if not self.quantity or self.quantity <= 0:
            return None
        if self.component_type == "powder":
            return self.quantity * self.GRAINS_PER_POUND
        return self.quantity

    @property
    def related_loads(self):
        """All loads that reference this order lot."""
        if self.component_type == "bullet":
            return list(self.bullet_loads)
        elif self.component_type == "powder":
            return list(self.powder_loads)
        elif self.component_type == "primer":
            return list(self.primer_loads)
        elif self.component_type == "casing":
            return list(self.casing_loads)
        return []

    @property
    def load_usage_details(self):
        """Build per-load usage and cost details for this lot."""
        details = []
        total_units = self.total_units

        for load in sorted(
            self.related_loads,
            key=lambda item: item.date_created or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        ):
            usage = load.lot_usage_breakdown.get(self.component_type)
            if usage and usage["lot"].id != self.id:
                usage = None

            consumed_units = usage["consumed_units"] if usage else None
            usage_percentage = usage["percentage"] if usage else None
            component_batch_cost = load.batch_cost_breakdown.get(self.component_type)
            estimated_batch_cost = load.batch_cost_breakdown.get("total")
            estimated_per_round = load.cost_breakdown.get("total")

            details.append(
                {
                    "load": load,
                    "consumed_units": consumed_units,
                    "total_units": total_units,
                    "usage_percentage": usage_percentage,
                    "estimated_component_batch_cost": component_batch_cost,
                    "estimated_batch_cost": estimated_batch_cost,
                    "estimated_per_round_cost": estimated_per_round,
                    "rounds_made": load.rounds_made,
                }
            )

        return details

    @property
    def tracked_used_units(self):
        """Sum of all known lot units consumed by tracked loads."""
        used_values = [
            detail["consumed_units"]
            for detail in self.load_usage_details
            if detail["consumed_units"] is not None
        ]
        return sum(used_values) if used_values else 0

    @property
    def tracked_used_percentage(self):
        """Percentage of the lot consumed by loads with known usage."""
        if not self.total_units:
            return None
        return (self.tracked_used_units / self.total_units) * 100

    @property
    def estimated_remaining_percentage(self):
        """Estimated remaining lot percentage when the lot is not depleted."""
        used_percentage = self.tracked_used_percentage
        if used_percentage is None:
            return None
        return max(0, 100 - used_percentage)

    @property
    def waste_percentage(self):
        """Percentage of the depleted lot not accounted for by tracked loads."""
        used_percentage = self.tracked_used_percentage
        if used_percentage is None:
            return None
        return max(0, 100 - used_percentage)

    @property
    def depleted_cost_comparison(self):
        """Compare estimated and waste-adjusted costs for depleted lots."""
        if not self.is_depleted or self.total_cost is None:
            return []

        tracked_used_units = self.tracked_used_units
        if not tracked_used_units:
            return []

        comparisons = []
        for detail in self.load_usage_details:
            consumed_units = detail["consumed_units"]
            load = detail["load"]
            if consumed_units is None or not load.rounds_made:
                continue

            estimated_component_batch_cost = detail["estimated_component_batch_cost"]
            true_component_batch_cost = self.total_cost * (
                consumed_units / tracked_used_units
            )

            estimated_batch_cost = detail["estimated_batch_cost"]
            if (
                estimated_batch_cost is not None
                and estimated_component_batch_cost is not None
            ):
                true_batch_cost = (
                    estimated_batch_cost
                    - estimated_component_batch_cost
                    + true_component_batch_cost
                )
            else:
                true_batch_cost = None

            true_per_round_cost = (
                true_batch_cost / load.rounds_made if true_batch_cost is not None else None
            )

            comparisons.append(
                {
                    "load": load,
                    "consumed_units": consumed_units,
                    "usage_percentage": detail["usage_percentage"],
                    "estimated_component_batch_cost": estimated_component_batch_cost,
                    "true_component_batch_cost": true_component_batch_cost,
                    "estimated_batch_cost": estimated_batch_cost,
                    "true_batch_cost": true_batch_cost,
                    "estimated_per_round_cost": detail["estimated_per_round_cost"],
                    "true_per_round_cost": true_per_round_cost,
                }
            )

        return comparisons

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
    rounds_made = db.Column(db.Integer, nullable=True)
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

    @property
    def batch_cost_breakdown(self):
        """Calculate per-component cost for the full batch."""
        if not self.rounds_made or self.rounds_made <= 0:
            return {
                "bullet": None,
                "powder": None,
                "primer": None,
                "casing": None,
                "total": None,
            }

        per_round_costs = self.cost_breakdown
        costs = {
            component: (
                per_round_costs[component] * self.rounds_made
                if per_round_costs[component] is not None
                else None
            )
            for component in ("bullet", "powder", "primer", "casing")
        }

        known = [v for v in costs.values() if v is not None]
        costs["total"] = sum(known) if known else None
        return costs

    @property
    def total_batch_cost(self):
        """Estimated total cost for all rounds made in this batch."""
        return self.batch_cost_breakdown["total"]

    @property
    def lot_usage_breakdown(self):
        """Calculate component lot consumption for the full batch."""
        usage = {
            "bullet": self._build_lot_usage(self.bullet_lot, units_per_round=1, unit_label="rounds"),
            "powder": self._build_lot_usage(
                self.powder_lot,
                units_per_round=self.powder_weight,
                unit_label="grains",
            ),
            "primer": self._build_lot_usage(self.primer_lot, units_per_round=1, unit_label="rounds"),
            "casing": self._build_lot_usage(self.casing_lot, units_per_round=1, unit_label="rounds"),
        }
        return usage

    def _build_lot_usage(self, lot, units_per_round, unit_label):
        """Build usage data for a component lot in the current batch."""
        if lot is None or not self.rounds_made or self.rounds_made <= 0:
            return None

        if units_per_round is None or units_per_round <= 0:
            return None

        if not lot.quantity or lot.quantity <= 0:
            return None

        if lot.component_type == "powder":
            total_units = lot.quantity * OrderLot.GRAINS_PER_POUND
        else:
            total_units = lot.quantity

        consumed_units = units_per_round * self.rounds_made
        percentage = (consumed_units / total_units) * 100 if total_units else None

        return {
            "lot": lot,
            "consumed_units": consumed_units,
            "total_units": total_units,
            "percentage": percentage,
            "unit_label": unit_label,
        }

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
        variance = sum((v - avg) ** 2 for v in velocities) / len(velocities)
        return round(variance**0.5, 2)

    @property
    def velocity_min(self):
        if not self.shots:
            return None
        velocities = [s.velocity for s in self.shots if s.velocity is not None]
        if not velocities:
            return None
        return round(min(velocities), 2)

    @property
    def velocity_max(self):
        if not self.shots:
            return None
        velocities = [s.velocity for s in self.shots if s.velocity is not None]
        if not velocities:
            return None
        return round(max(velocities), 2)

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

