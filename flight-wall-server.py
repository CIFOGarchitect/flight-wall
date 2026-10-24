#!/usr/bin/env python3
"""Flight Wall aggregator — one combined ADS-B feed from five open sources.

Why this exists: browsers often refuse to call these feeds directly
(sandboxed previews block the calls, and some feeds don't send the CORS
headers browsers require). Server-side fetching has neither problem, so
this script pulls every source at the same time, merges the results, and
serves the flight-wall page, one aggregated JSON feed, and a /api/geocode
place lookup (OpenStreetMap Nominatim).

HOW TO RUN (keep this file in the same folder as flight-wall.html):
  Mac / Linux:   python3 flight-wall-server.py
  Windows:       py flight-wall-server.py
                 (install Python first if needed: python.org or Microsoft Store)
Then open http://localhost:8000 in your browser (not in a chat preview).
The server listens on all network interfaces, so any device on the same
Wi-Fi can open the board too: on a smart TV's browser, open the TV
address printed when the server starts (e.g. http://192.168.1.42:8000
or http://10.0.0.15:8000).
Allow Python through the firewall when prompted, keep the computer awake,
and keep the TV and computer on the same Wi-Fi.

To host it in the cloud instead (e.g. Render's free tier), see
DEPLOY_RENDER.md — no code changes needed; Render sets PORT itself.

No API keys, no installs beyond Python 3 itself — only the standard library.

Sources, fetched in parallel on every refresh (15s from the page):
  1. airplanes.live    (point query)
  2. adsb.lol          (point query)
  3. adsb.fi           (point query, v3)
  4. AvioADSB          (point query)
  5. OpenSky Network   (bounding box; listed last — anonymous
                        requests are the most rate-limit prone)
Aircraft are deduplicated by ICAO hex address; if several feeds see the
same plane, the first feed in the list above wins and the rest are noted.
If a feed is down, the others still fill the board.
"""

import json
import math
import os
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

# Port: hosts like Render assign one via PORT; FLIGHT_WALL_PORT is the
# manual override; otherwise 8000.
PORT = int(os.environ.get("PORT")
           or os.environ.get("FLIGHT_WALL_PORT")
           or "8000")
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "flight-wall.html")
USER_AGENT = "FlightWall/1.0 (personal flight board)"
FETCH_TIMEOUT = 10  # seconds per source; all five run in parallel


def haversine_mi(lat1, lon1, lat2, lon2):
    r = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        if resp.status != 200:
            raise RuntimeError("HTTP %s" % resp.status)
        return json.loads(resp.read().decode("utf-8"))


def _num(value):
    return value if isinstance(value, (int, float)) else None


def fetch_opensky(lat, lon, radius_mi):
    dlat = radius_mi / 69.0
    dlon = radius_mi / (69.0 * math.cos(math.radians(lat)))
    url = ("https://opensky-network.org/api/states/all"
           "?lamin=%.4f&lamax=%.4f&lomin=%.4f&lomax=%.4f"
           % (lat - dlat, lat + dlat, lon - dlon, lon + dlon))
    data = fetch_json(url)
    out = []
    for s in data.get("states") or []:
        if s[5] is None or s[6] is None or s[8]:
            continue  # no position, or on the ground
        alt_m = s[7] if s[7] is not None else s[13]
        out.append({
            "hex": s[0],
            "callsign": (s[1] or "").strip() or ("ICAO " + s[0].upper()),
            # OpenSky category is index 17 (0-20); map the useful ones to
            # ADS-B letters. OpenSky sends no type code or model name.
            "category": {2: "A1", 3: "A2", 4: "A3", 5: "A4", 6: "A5",
                         7: "A6", 8: "A7", 9: "B1"}.get(s[17]),
            "ac_type": None,
            "model": None,
            "alt_ft": round(alt_m * 3.28084) if alt_m is not None else None,
            "spd_kt": round(s[9] * 1.94384) if s[9] is not None else None,
            "hdg": s[10],
            "vs_fpm": round(s[11] * 196.85) if s[11] is not None else None,
            "lat": s[6],
            "lon": s[5],
        })
    return out


def fetch_adsb(base, path, lat, lon, radius_mi):
    nm = round(radius_mi / 1.15078)
    url = base + path.format(lat="%.4f" % lat, lon="%.4f" % lon, nm=nm)
    data = fetch_json(url)
    out = []
    for a in data.get("ac") or data.get("aircraft") or []:
        if not isinstance(a, dict):
            continue
        if a.get("lat") is None or a.get("lon") is None:
            continue
        if a.get("alt_baro") == "ground":
            continue
        alt = _num(a.get("alt_baro"))
        if alt is None:
            alt = _num(a.get("alt_geom"))
        vs = a.get("baro_rate")
        if vs is None:
            vs = a.get("geom_rate")
        if vs is None:
            vs = a.get("vert_rate")
        out.append({
            "hex": a.get("hex", ""),
            "callsign": (a.get("flight") or "").strip()
                        or ("ICAO " + (a.get("hex") or "").upper()),
            "category": a.get("category"),
            "ac_type": (a.get("t") or "").strip() or None,
            # Plain-English model only (desc). The type code stays in ac_type
            # so the page can fall back to it when no description exists;
            # keeping them separate lets the merge prefer the description.
            "model": a.get("desc") or None,
            "alt_ft": round(alt) if alt is not None else None,
            "spd_kt": round(a["gs"]) if _num(a.get("gs")) is not None else None,
            "hdg": a.get("track"),
            "vs_fpm": round(vs) if _num(vs) is not None else None,
            "lat": a["lat"],
            "lon": a["lon"],
        })
    return out


# (name, fetch function) in priority order for dedupe: first feed wins.
# OpenSky sits last: its anonymous requests are the most rate-limit prone.
SOURCE_DEFS = [
    ("airplanes.live", lambda la, lo, r: fetch_adsb(
        "https://api.airplanes.live",
        "/v2/point/{lat}/{lon}/{nm}", la, lo, r)),
    ("adsb.lol", lambda la, lo, r: fetch_adsb(
        "https://api.adsb.lol",
        "/v2/point/{lat}/{lon}/{nm}", la, lo, r)),
    ("adsb.fi", lambda la, lo, r: fetch_adsb(
        "https://opendata.adsb.fi/api",
        "/v3/lat/{lat}/lon/{lon}/dist/{nm}", la, lo, r)),
    ("AvioADSB", lambda la, lo, r: fetch_adsb(
        "https://avioadsb.org",
        "/v1/point/{lat}/{lon}/{nm}", la, lo, r)),
    ("OpenSky", fetch_opensky),
]


def aggregate(lat, lon, radius_mi):
    """Fetch all sources at once; merge into one deduplicated feed."""
    with ThreadPoolExecutor(max_workers=len(SOURCE_DEFS)) as pool:
        futures = [(name, pool.submit(fn, lat, lon, radius_mi))
                   for name, fn in SOURCE_DEFS]
        results = []
        for name, fut in futures:
            try:
                results.append((name, True, fut.result(), None))
            except Exception as exc:  # noqa: BLE001 - report, don't crash
                results.append((name, False, [], str(exc)))

    merged = {}
    for name, _ok, records, _err in results:
        for rec in records:
            key = (rec["hex"] or "").lower()
            if not key:
                continue
            if key not in merged:
                merged[key] = dict(rec, sources=[name])
            else:
                if name not in merged[key]["sources"]:
                    merged[key]["sources"].append(name)
                # Fill in category/type/model from a later feed when the
                # first feed's record didn't carry them (e.g. OpenSky never
                # sends a model; adsb.lol sends no plain-English description).
                if not merged[key].get("category") and rec.get("category"):
                    merged[key]["category"] = rec["category"]
                if not merged[key].get("ac_type") and rec.get("ac_type"):
                    merged[key]["ac_type"] = rec["ac_type"]
                if not merged[key].get("model") and rec.get("model"):
                    merged[key]["model"] = rec["model"]

    flights = []
    for rec in merged.values():
        rec["dist_mi"] = round(
            haversine_mi(lat, lon, rec["lat"], rec["lon"]), 1)
        flights.append(rec)
    flights.sort(key=lambda f: f["dist_mi"])

    return {
        "flights": flights,
        "sources": [
            {"name": name, "ok": ok, "count": len(records), "error": err}
            for name, ok, records, err in results
        ],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    def _send(self, status, body, content_type):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/geocode":
            qs = parse_qs(parsed.query)
            q = (qs.get("q", [""])[0] or "").strip()
            if not q:
                return self._send(400, "missing q", "text/plain")
            try:
                data = fetch_json(
                    "https://nominatim.openstreetmap.org/search"
                    "?format=json&addressdetails=1&limit=1&q=" + quote(q))
            except Exception:
                data = None
            if data:
                first = data[0]
                payload = {
                    "found": True,
                    "lat": float(first["lat"]),
                    "lon": float(first["lon"]),
                    "display_name": first.get("display_name", ""),
                    "address": first.get("address", {}),
                }
            else:
                payload = {"found": False}
            return self._send(200, json.dumps(payload), "application/json")

        if parsed.path == "/api/flights":
            qs = parse_qs(parsed.query)
            try:
                lat = float(qs.get("lat", ["41.7370"])[0])
                lon = float(qs.get("lon", ["-111.8338"])[0])
                radius = float(qs.get("radius", ["50"])[0])
            except ValueError:
                return self._send(400, "bad lat/lon/radius", "text/plain")
            payload = aggregate(lat, lon, radius)
            return self._send(200, json.dumps(payload), "application/json")

        if parsed.path in ("/", "/flight-wall.html"):
            if not os.path.exists(PAGE):
                return self._send(
                    500,
                    "flight-wall.html not found next to flight-wall-server.py",
                    "text/plain")
            with open(PAGE, "rb") as fh:
                return self._send(200, fh.read(), "text/html")

        if parsed.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")

        return self._send(404, "not found", "text/plain")


def _lan_ip():
    """Best-effort LAN address for other devices (TVs, tablets) on the
    same Wi-Fi. The UDP connect sends no traffic; it just reveals which
    local address would be used."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def main():
    # 0.0.0.0 = listen on all interfaces, so the TV and other devices on
    # the same Wi-Fi can reach the board (127.0.0.1 would be this PC only).
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print("Flight Wall aggregator running.")
    print("  This computer:  http://localhost:%d" % PORT)
    lan = _lan_ip()
    if lan:
        print("  Other devices on your Wi-Fi (e.g. smart TV):  http://%s:%d" % (lan, PORT))
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
