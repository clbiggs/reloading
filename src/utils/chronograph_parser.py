"""Parser for Velocity Pro Radar Chronograph XLSX export files."""

import json
import re
import zipfile
import xml.etree.ElementTree as ET


def parse_chronograph_xlsx(file_stream):
    """
    Parse a Velocity Pro Radar Chronograph XLSX export file.

    Returns a dict with:
      - weather: {temperature, humidity, pressure, altitude}
      - summary: {type, projectile_weight, avg_velocity, min_velocity,
                   max_velocity, std_dev, extreme_spread, avg_power_factor,
                   avg_kinetic_energy, session_notes}
      - shots: list of dicts with {shot_number, speed, deviation,
                kinetic_energy, power_factor, time, clean_bore,
                cold_bore, notes}
    """
    z = zipfile.ZipFile(file_stream)
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

    # Build a dict of cell_ref -> value
    cells = {}
    for row in sheet_root.findall(".//s:row", ns):
        for c in row.findall("s:c", ns):
            ref = c.get("r")
            t = c.get("t")
            v = c.find("s:v", ns)
            val = v.text if v is not None else ""
            if t == "s":
                val = strings[int(val)] if val else ""
            cells[ref] = val

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

    # Parse summary data
    summary = {}
    summary["type"] = cells.get("A40", "").strip()

    pw = cells.get("B41", "")
    pw_match = re.search(r"([\d.]+)", pw)
    if pw_match:
        summary["projectile_weight"] = float(pw_match.group(1))

    avg_v = cells.get("B42", "")
    avg_v_match = re.search(r"([\d.]+)", avg_v)
    if avg_v_match:
        summary["avg_velocity"] = float(avg_v_match.group(1))

    min_v = cells.get("B43", "")
    min_v_match = re.search(r"([\d.]+)", min_v)
    if min_v_match:
        summary["min_velocity"] = float(min_v_match.group(1))

    max_v = cells.get("B44", "")
    max_v_match = re.search(r"([\d.]+)", max_v)
    if max_v_match:
        summary["max_velocity"] = float(max_v_match.group(1))

    sd = cells.get("B45", "")
    if sd:
        try:
            summary["std_dev"] = float(sd)
        except ValueError:
            pass

    es = cells.get("B46", "")
    if es:
        try:
            summary["extreme_spread"] = float(es)
        except ValueError:
            pass

    apf = cells.get("B47", "")
    apf_match = re.search(r"([\d.]+)", apf)
    if apf_match:
        summary["avg_power_factor"] = float(apf_match.group(1))

    ake = cells.get("B48", "")
    ake_match = re.search(r"([\d.]+)", ake)
    if ake_match:
        summary["avg_kinetic_energy"] = float(ake_match.group(1))

    summary["session_notes"] = cells.get("B49", "").strip()

    # Parse shot data - starts at row 52
    shots = []
    row_num = 52
    while True:
        shot_num_val = cells.get(f"A{row_num}", "")
        if not shot_num_val:
            break
        try:
            shot_num = int(float(shot_num_val))
        except (ValueError, TypeError):
            break

        speed_val = cells.get(f"B{row_num}", "")
        dev_val = cells.get(f"C{row_num}", "")
        ke_val = cells.get(f"D{row_num}", "")
        pf_val = cells.get(f"E{row_num}", "")
        time_val = cells.get(f"F{row_num}", "")
        clean_bore = cells.get(f"G{row_num}", "").strip()
        cold_bore = cells.get(f"H{row_num}", "").strip()
        shot_notes = cells.get(f"I{row_num}", "").strip()

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
            "timestamp": time_val.strip() if time_val else None,
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


def _extract_value(text, pattern):
    """Extract a value from text using a regex pattern."""
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None


def _safe_float(val):
    """Safely convert a value to float."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

