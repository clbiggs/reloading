# Reloading Tracker

A web application for managing and tracking ammunition reloading data. Built with Flask, SQLite, and Bootstrap 5 — runs in a single Docker container with persistent data storage.

## Features

- **Component Management** — Manage calibers, primer types, manufacturers, bullets, primers, powders, casings, and factory ammo with full CRUD operations
- **Order Lot Tracking** — Track purchases of bullets, powder, primers, casings, and factory ammo with lot numbers, costs, and quantities
- **Recipe Management** — Create reusable recipes with a custom name, component selection, and powder charge weight
- **Load Tracking** — Create loads from a recipe, linking the component order lots used with batch measurements, discarded component waste, and true cost per round
- **Firearm Registry** — Track firearms with caliber, barrel length, twist rate, and notes
- **Test Sessions** — Record chronograph test sessions with weather data, shot groups, and individual shot velocities
- **Chronograph Import** — Upload `.xlsx` exports from the Velocity Pro Radar Chronograph to automatically create test sessions with shot data
- **Summaries** — View aggregate statistics filtered by firearm, bullet, or powder
- **Responsive Design** — Works on both desktop and mobile browsers (dark theme)
- **Density Altitude** — Automatically calculated from temperature, humidity, and pressure

## Quick Start

### Using Docker Compose (recommended)

```bash
docker compose up -d
```

The application will be available at **http://localhost:5000**

### Using Docker directly

```bash
docker build -t reloading-tracker .
docker run -d \
  --name reloading-tracker \
  -p 5000:5000 \
  -v reloading-data:/data \
  -e SECRET_KEY=your-secret-key \
  reloading-tracker
```

## Data Persistence

All data is stored in a SQLite database at `/data/reloading.db` inside the container. The Docker Compose configuration mounts a named volume (`reloading-data`) to `/data`, ensuring your data persists across container restarts and upgrades.

## Precision

- **Grain weights** — 2 decimal places (e.g. `147.00 gr`)
- **Inch lengths and MOA** — 4 decimal places (e.g. `2.8000 in`)
- **Velocity** — 2 decimal places (e.g. `961.84 fps`)

## Chronograph Import

The application supports importing `.xlsx` files exported from the **Velocity Pro Radar Chronograph**. The import automatically extracts:

- Weather conditions (temperature, humidity, pressure)
- Individual shot data (velocity, deviation, kinetic energy, power factor, timestamps)
- Clean bore / cold bore indicators (stored as trace data)

During import, you can optionally associate the session with a firearm, load, location, and range distance.

## Project Structure

```
├── Dockerfile
├── docker-compose.yml
├── src/
│   ├── app.py                  # Flask application factory
│   ├── models.py               # SQLAlchemy database models
│   ├── database.py             # Database initialization
│   ├── requirements.txt        # Python dependencies
│   ├── routes/                 # Route blueprints
│   │   ├── calibers.py
│   │   ├── primer_types.py
│   │   ├── manufacturers.py
│   │   ├── primers.py
│   │   ├── bullets.py
│   │   ├── casings.py
│   │   ├── powders.py
│   │   ├── order_lots.py
│   │   ├── loads.py
│   │   ├── firearms.py
│   │   ├── test_sessions.py
│   │   ├── upload.py
│   │   └── summaries.py
│   ├── templates/              # Jinja2 HTML templates
│   └── utils/
│       ├── chronograph_parser.py
│       └── calculations.py
└── sample_data/
    └── chronograph_exports/    # Example chronograph export files
```

## Technology Stack

- **Backend**: Python 3.12, Flask 3.1, SQLAlchemy 2.0
- **Database**: SQLite
- **Frontend**: Bootstrap 5.3 (dark theme), Bootstrap Icons
- **Server**: Gunicorn
- **Container**: Docker

