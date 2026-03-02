"""Calculation utilities for reloading data."""

import math


def calculate_density_altitude(temperature_f, humidity_pct, pressure_inhg):
    """
    Calculate density altitude from temperature (°F), humidity (%),
    and barometric pressure (inHg).

    Returns density altitude in feet.
    """
    if temperature_f is None or pressure_inhg is None:
        return None

    # Convert temperature to Celsius
    temp_c = (temperature_f - 32) * 5 / 9

    # Convert pressure to millibars
    pressure_mb = pressure_inhg * 33.8639

    # Calculate station pressure (assuming sea level for simplicity)
    # Calculate vapor pressure using Magnus formula
    if humidity_pct is not None and humidity_pct > 0:
        es = 6.1078 * math.pow(10, (7.5 * temp_c) / (237.3 + temp_c))
        vapor_pressure = (humidity_pct / 100.0) * es
    else:
        vapor_pressure = 0

    # Calculate virtual temperature in Kelvin
    tv_k = (temp_c + 273.15) / (1 - 0.3783 * vapor_pressure / pressure_mb)

    # Standard atmosphere values
    t0 = 288.15  # Standard temp at sea level in K
    p0 = 1013.25  # Standard pressure at sea level in mb
    lapse_rate = 0.0065  # K/m

    # Pressure altitude in meters
    pressure_alt_m = (1 - math.pow(pressure_mb / p0, 0.190284)) * 44330.77

    # Density altitude
    density_alt_m = pressure_alt_m + (t0 / lapse_rate) * (
        1 - math.pow(t0 / tv_k, 0.234969)
    )

    # Convert to feet
    density_alt_ft = density_alt_m * 3.28084

    return round(density_alt_ft, 0)

