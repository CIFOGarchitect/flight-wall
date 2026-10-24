# Flight Wall

A live, airport-style departure board for aircraft flying near you. Open it in a browser, put it on a second monitor or a TV, and watch nearby traffic update every 15 seconds.

No accounts, no API keys, no installs beyond Python itself. The data comes from free, volunteer-run ADS-B receiver networks.

## What's in this folder

- `flight-wall.html` — the board itself (the page you look at).
- `flight-wall-server.py` — a small server that pulls five free ADS-B feeds at once, merges them into one feed, and serves the board. This is what makes the board reliable: if one feed is down, the others still fill it.
- `README.md` — this file.

## What you need

- A computer (Windows, Mac, or Linux) on Wi-Fi.
- Python 3. Check by opening a terminal and running `python3 --version` (Mac/Linux) or `py --version` (Windows). If you don't have it, get it free from python.org (on Windows, the Microsoft Store works too).

## Run it

1. Put all three files in one folder.
2. Open a terminal in that folder:
   - Windows: open the folder, click the address bar, type `cmd`, press Enter. (Or Shift + right-click in the folder → "Open PowerShell window here".)
   - Mac: right-click the folder → "New Terminal at Folder". (Or open Terminal and `cd` into the folder.)
   - Linux: open a terminal in the folder.
3. Start the server:
   - Windows: `py flight-wall-server.py`
   - Mac/Linux: `python3 flight-wall-server.py`
4. Leave that terminal window open while you use the board. To stop the server, press Ctrl+C in the terminal.

## Open it

In a browser (Chrome, Edge, Safari, or Firefox), go to:

**http://localhost:8000**

Open it in a real browser window — not inside a chat app preview or an embedded panel, which blocks the data.

## What you'll see

- One row per aircraft, nearest first: callsign, type (rotor or fixed wing), altitude, speed, heading, distance, and climb/descent rate.
- Type comes from the ADS-B emitter category when the feed provides it (A7 = rotorcraft), plus known helicopter type codes; rows from feeds without that data show —.
- The nearest aircraft is highlighted.
- The header shows your center location and the Air Route Traffic Control Center (ARTCC) for that airspace, e.g. SALT LAKE CENTER (ZLC). The Center shown is approximate (nearest Center facility).
- The status line shows which data sources are alive, e.g. "Aggregated feed · 4/5 sources · 23 aircraft".
- Airline badges appear next to airline callsigns when a logo is available; if a logo doesn't load, the airline name still shows.

## Controls

- Range: 25, 50, or 100 miles, or "Custom…" for any range from 5–250 miles.
- "Name this place…" + "★ Save favorite": save a place (e.g. an airport or a town) and jump back to it from "★ Saved places…".
- "Use my location": center the board on your device's location (your browser will ask permission).
- "City, State" + "Go": type a city and state (e.g. Boise, ID) and hit Go (or Enter) to center the board there — for devices where location permission is blocked or unavailable. The lookup runs through the server when it's available, or straight to OpenStreetMap's Nominatim otherwise. Once centered, ★ Save favorite keeps it like any other place.
- "Logan": jump back to the default home location.
- "Demo flights": simulated traffic, so you can see the board layout even with no live data.
- "Big display": toggles to a large single-aircraft view showing only the nearest aircraft above 15,000 ft AGL (approximate — see Limits) — built for a TV across the room. Press it again to return to the full board. The aircraft model shows beside the AGL figure when the feed provides it.
- "Fullscreen": fills the screen. On a computer, F11 does the same.

## Put it on a smart TV

Your computer stays on and runs the server; the TV just displays the board.

**If the TV has a web browser:** when the server starts, it prints two addresses. The second one is for other devices on your Wi-Fi — open that one in the TV's browser (for example http://192.168.1.42:8000 or http://10.0.0.15:8000). Don't type `localhost` on the TV — on the TV, that means the TV itself. Keep the TV and computer on the same Wi-Fi (not a guest network).

**If the TV has no browser:** cast it or cable it.
- Cast: in Chrome on your computer, open the board, click the three-dot menu → Cast → pick your TV (needs a Chromecast built-in or dongle, or an AirPlay-compatible TV).
- HDMI: connect the computer to the TV with an HDMI cable, switch the TV to that input, and open the board fullscreen.

In all cases, if the computer sleeps, the board freezes — set it to stay awake while the board is up.

## Change the home location

The default center is Logan, UT. To make it yours: open `flight-wall.html` in a text editor, find the line starting with `var HOME =`, and change the name and coordinates to your town or airport. Save, restart the server, and the board opens on your location.

## Troubleshooting

- "Aggregator unreachable" — the server isn't running. Start it first (see "Run it"), then reload the page.
- "Failed to fetch" on every source, or a blank board — you're probably opening the file in a preview or from a file path. Use http://localhost:8000 in a real browser.
- Your computer asks about Python and the firewall — allow it on private networks, or other devices (like a TV) can't reach the board.
- "Port already in use" — something else is using port 8000. Start with a different port instead: Windows: `set FLIGHT_WALL_PORT=8001 && py flight-wall-server.py`; Mac/Linux: `FLIGHT_WALL_PORT=8001 python3 flight-wall-server.py`. Then open http://localhost:8001.
- "No aircraft currently reporting" — a quiet sky, normal at night or in a remote area. Try a wider range.
- Fewer than 5/5 sources — normal. Feeds go down and come back; the board works off whichever ones are up.
- Board stops updating — check the computer hasn't gone to sleep.

## Limits worth knowing

- Coverage comes from volunteer ADS-B receivers, so some aircraft won't appear, especially low or far from a receiver.
- The free feeds don't include origin/destination — that takes a paid flight-data service.
- The controlling Center is approximate (nearest Center facility). Near a boundary, the true controlling Center may differ.
- The big display's 15,000 ft AGL threshold is approximate: feeds report MSL altitude, and AGL is estimated using Logan field elevation (4,457 ft) as the ground reference — exact near Logan, approximate elsewhere.

Enjoy the board — and look up once in a while. The real ones are overhead.

## Hosting it online
Want a public link someone else can open (no computer to keep on)? See DEPLOY_RENDER.md — it uses Render's free tier.
