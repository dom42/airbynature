# AirByNature

Home Assistant integration for AirByNature ventilation systems, using the
AirByNature cloud (the same account as the AirByNature app).

## Installation

1. In HACS, open **Integrations → ⋮ → Custom repositories** and add
   `https://github.com/dom42/airbynature` with category **Integration**.
2. Install **AirByNature** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → AirByNature** and
   sign in with your AirByNature app e-mail and password.

## What you get

Each address in your account becomes a device (for example "Gerdavej 14").
Each ventilation unit at that address becomes a device linked to it.

**Address device**

- Sensors: average temperature, mode, current rule, inlets paused until,
  paused until (disabled by default), status
- Binary sensors: rule enabled, drying
- Controls: target temperature (0–40 °C), pause inlets (hours, 0 stops the pause)

**Unit device**

- Sensors: inlet, outlet and outdoor temperature; inlet and outlet humidity;
  CO2 (ppm); TVOC (ppb); inlet and outlet fan (%); fan speeds (rpm)
- Diagnostics: last measurement, Wi-Fi signal, speed factors, measurement
  interval, online, filter, drying heat exchanger
- Control: comfort level (off, very quiet, quiet, normal, high, extra high)

Controls only appear when your account is allowed to use them.

Data is polled every 60 seconds.

## Upgrading from 0.0.1

Remove the old AirByNature integration entry, then add it again. Entity IDs
change in this version.

## Known limitations

- Pause schedules, the schedule and history are not exposed.
- Mode is read-only.
- The Wi-Fi signal is shown as the raw value from the API.
