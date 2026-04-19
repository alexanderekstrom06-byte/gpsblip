import glob
import time


def nmea_to_decimal(raw_value, direction):
    if not raw_value or not direction:
        return None
    try:
        if direction in ("N", "S"):
            deg_len = 2
        elif direction in ("E", "W"):
            deg_len = 3
        else:
            return None
        degrees = float(raw_value[:deg_len])
        minutes = float(raw_value[deg_len:])
        decimal = degrees + (minutes / 60.0)
        if direction in ("S", "W"):
            decimal = -decimal
        return decimal
    except (TypeError, ValueError):
        return None


def parse_nmea_lat_lon(nmea_line):
    if not nmea_line.startswith("$G"):
        return None

    parts = nmea_line.split(",")
    if len(parts) < 7:
        return None

    sentence_type = parts[0]

    if sentence_type.endswith("RMC"):
        status = parts[2]
        if status != "A":
            return None
        lat = nmea_to_decimal(parts[3], parts[4])
        lon = nmea_to_decimal(parts[5], parts[6])
    elif sentence_type.endswith("GGA"):
        quality = parts[6]
        if quality in ("", "0"):
            return None
        lat = nmea_to_decimal(parts[2], parts[3])
        lon = nmea_to_decimal(parts[4], parts[5])
    else:
        return None

    if lat is None or lon is None:
        return None

    return lat, lon


def guess_gps_ports():
    # macOS and Linux/Raspberry Pi serial patterns
    patterns = [
        "/dev/tty.*",
        "/dev/cu.*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/serial*",
    ]
    candidates = sorted(set(path for pattern in patterns for path in glob.glob(pattern)))

    preferred = []
    fallback = []
    for port in candidates:
        name = port.lower()
        if any(keyword in name for keyword in ("ublox", "u-blox", "usbserial", "wchusbserial", "gps", "vk", "ttyusb", "ttyacm", "serial")):
            preferred.append(port)
        else:
            fallback.append(port)
    return preferred + fallback


def get_origin_from_usb_gps(port=None, timeout_seconds=20, baudrate=9600):
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial mangler. Installer med: .venv/bin/pip install pyserial") from exc

    ports_to_try = [port] if port else guess_gps_ports()
    if not ports_to_try:
        raise RuntimeError("Ingen serielle porte fundet til GPS-modtager.")

    deadline = time.time() + timeout_seconds
    last_error = None

    for gps_port in ports_to_try:
        try:
            with serial.Serial(gps_port, baudrate=baudrate, timeout=1) as ser:
                print(f"Forsøger at læse GPS fra {gps_port}...")
                while time.time() < deadline:
                    raw = ser.readline().decode("ascii", errors="ignore").strip()
                    if not raw:
                        continue
                    coords = parse_nmea_lat_lon(raw)
                    if coords:
                        lat, lon = coords
                        return f"{lat:.6f},{lon:.6f}", gps_port
        except Exception as exc:  # pylint: disable=broad-except
            last_error = exc
            continue

    if last_error:
        raise RuntimeError(f"Kunne ikke læse gyldig GPS-position. Sidste fejl: {last_error}") from last_error
    raise RuntimeError("Kunne ikke læse gyldig GPS-position fra de fundne porte.")
