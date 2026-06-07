"""Parser for Velocity Pro Radar Chronograph XLSX export files."""

from datetime import datetime, timedelta
import json
import re
import zipfile
import xml.etree.ElementTree as ET


def parse_chronograph_xlsx(file_stream):
    """
    Parse a Velocity Pro Radar Chronograph XLSX export file.

    Returns a dict with:
      - weather: {temperature, humidity, pressure, altitude}
      - summary: {type, date, time, projectile_weight, avg_velocity, min_velocity,
                   max_velocity, std_dev, extreme_spread, avg_power_factor,
                   avg_kinetic_energy, session_notes}
      - shots: list of dicts with {shot_number, speed, deviation,
                kinetic_energy, power_factor, time, clean_bore,
                cold_bore, notes}
    """
    with zipfile.ZipFile(file_stream) as z:
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        # Read shared strings
        ss_xml = z.read("xl/sharedStrings.xml")
        root = ET.fromstring(ss_xml)
        strings = []
        for si in root.findall(".//s:si", ns):
            parts = []
            for t in si.findall(".//s:t", ns):
                if t.text:
                    parts.append(t.text)
            strings.append("".join(parts))

        # Read sheet1
        sheet_xml = z.read("xl/worksheets/sheet1.xml")
        sheet_root = ET.fromstring(sheet_xml)

    # Build a dict of cell_ref -> value and row/column -> value.
    cells = {}
    rows = {}
    for row in sheet_root.findall(".//s:row", ns):
        row_num = int(row.get("r"))
        row_values = {}
        for c in row.findall("s:c", ns):
            ref = c.get("r")
            t = c.get("t")
            v = c.find("s:v", ns)
            val = v.text if v is not None else ""
            if t == "s":
                val = strings[int(val)] if val else ""
            col = _cell_column(ref)
            cells[ref] = val
            row_values[col] = val
        rows[row_num] = row_values

    # Parse weather data
    weather = {}
    temp_match = _extract_value(cells.get("A21", ""), r"Temperature,\s*f°:\s*([\d.]+)")
    if temp_match:
        weather["temperature"] = float(temp_match)

    humidity_match = _extract_value(cells.get("A22", ""), r"Humidity,\s*%:\s*([\d.]+)")
    if humidity_match:
        weather["humidity"] = float(humidity_match)

    pressure_match = _extract_value(
        cells.get("A23", ""), r"Pressure,\s*in-hg:\s*([\d.]+)"
    )
    if pressure_match:
        weather["pressure"] = float(pressure_match)

    altitude_match = _extract_value(
        cells.get("A24", ""), r"Altitude,\s*ft:\s*([\d.]+)"
    )
    if altitude_match:
        weather["altitude"] = float(altitude_match)

    summary_start_row = _find_row_with_value(rows, "A", "Pistol", "Rifle")

    # Parse summary data. Older exports place the summary values at fixed rows;
    # newer Rifle exports add Date/Time rows before Projectile weight, which shifts
    # the rest of the summary and shot table down. Read summary rows by label so
    # both layouts import correctly.
    summary = {}
    if summary_start_row:
        summary["type"] = str(rows[summary_start_row].get("A", "")).strip()
    else:
        summary["type"] = cells.get("A40", "").strip()

    summary_labels = {
        "Date": ("date", _safe_date),
        "Time": ("time", lambda val: str(val).strip()),
        "Projectile weight": ("projectile_weight", _first_number),
        "Average velocity": ("avg_velocity", _first_number),
        "Minimum velocity": ("min_velocity", _first_number),
        "Maximum velocity": ("max_velocity", _first_number),
        "Standard deviation": ("std_dev", _safe_float),
        "Extreme spread": ("extreme_spread", _safe_float),
        "Average power factor": ("avg_power_factor", _first_number),
        "Average kinetic energy": ("avg_kinetic_energy", _first_number),
        "Session notes": ("session_notes", lambda val: str(val).strip()),
    }

    for row_values in rows.values():
        label = str(row_values.get("A", "")).strip()
        if label not in summary_labels:
            continue
        key, parser = summary_labels[label]
        parsed_value = parser(row_values.get("B", ""))
        if parsed_value is not None:
            summary[key] = parsed_value

    summary.setdefault("session_notes", "")

    # Parse shot data. Locate the SHOT # header instead of assuming row 51/52.
    shots = []
    shot_header_row = _find_row_with_value(rows, "A", "SHOT #")
    row_num = (shot_header_row + 1) if shot_header_row else 52
    while True:
        row_values = rows.get(row_num, {})
        shot_num_val = row_values.get("A", "")
        if not shot_num_val:
            break
        try:
            shot_num = int(float(shot_num_val))
        except (ValueError, TypeError):
            break

        speed_val = row_values.get("B", "")
        dev_val = row_values.get("C", "")
        ke_val = row_values.get("D", "")
        pf_val = row_values.get("E", "")
        time_val = row_values.get("F", "")
        clean_bore = str(row_values.get("G", "")).strip()
        cold_bore = str(row_values.get("H", "")).strip()
        shot_notes = str(row_values.get("I", "")).strip()

        trace = {}
        if clean_bore:
            trace["clean_bore"] = True
        if cold_bore:
            trace["cold_bore"] = True

        shot = {
            "shot_number": shot_num,
            "velocity": _safe_float(speed_val),
            "deviation": _safe_float(dev_val),
            "kinetic_energy": _safe_float(ke_val),
            "power_factor": _safe_float(pf_val),
            "timestamp": str(time_val).strip() if time_val else None,
            "trace_data": json.dumps(trace) if trace else None,
            "notes": shot_notes if shot_notes else None,
        }
        shots.append(shot)
        row_num += 1

    return {
        "weather": weather,
        "summary": summary,
        "shots": shots,
    }


def _cell_column(cell_ref):
    """Return the column letters from an XLSX cell reference."""
    return re.sub(r"\d+", "", cell_ref or "")


def _find_row_with_value(rows, column, *values):
    """Find the first row where column equals one of the given values."""
    expected = {str(value).strip().casefold() for value in values}
    for row_num in sorted(rows):
        actual = str(rows[row_num].get(column, "")).strip().casefold()
        if actual in expected:
            return row_num
    return None


def _first_number(val):
    """Extract the first numeric value from a cell value."""
    if val is None:
        return None
    match = re.search(r"([\d.]+)", str(val))
    if match:
        return float(match.group(1))
    return None


def _extract_value(text, pattern):
    """Extract a value from text using a regex pattern."""
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None


def _safe_date(val):
    """Parse common XLSX date values into an ISO date string."""
    if val is None or val == "":
        return None

    text = str(val).strip()
    try:
        serial = float(text)
    except ValueError:
        serial = None

    if serial is not None:
        return (datetime(1899, 12, 30) + timedelta(days=serial)).date().isoformat()

    for date_format in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue

    return text


def _safe_float(val):
    """Safely convert a value to float."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
