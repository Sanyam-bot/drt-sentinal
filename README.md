# Transit Sentinel

> **Passive IoT telemetry that turns anonymous Wi-Fi and BLE probe requests into a real-time Origin-Destination (OD) matrix for Durham Region Transit fleets - no cameras, no tap-offs, no privacy trade-offs.**

---

## The Problem vs. The Solution

### The Problem - APCs Only Count Heads

Modern transit buses are fitted with **Automated Passenger Counters (APCs)** that use infrared beams or pressure mats at the doors. They answer one question well:

> *"How many people boarded or alighted at this stop?"*

What APCs **cannot** tell you is:

- Where did each passenger actually travel from and to?
- Which door did they use?
- How long was their journey on the vehicle?

Without this data, route planners are flying blind when optimising schedules and capacity.

### The Solution - Passive OD Matrix via RF Telemetry

Transit Sentinel solves this by exploiting a behaviour that is already happening on every bus: **passengers' smartphones continuously broadcast Wi-Fi and BLE probe requests** as they search for known networks.

Two Raspberry Pi sensor nodes (Front door and Rear door) passively capture these signals and measure their **Received Signal Strength Indicator (RSSI)**. By comparing the signal strength seen by each node at the moment a passenger boards and again when they alight, the system determines:

- **Boarding door** - stronger RSSI at Front or Rear sensor at first contact?
- **Alighting door** - stronger RSSI at which sensor at last contact?
- **GPS coordinates** for both events - pulled from the live DRT GTFS-Realtime feed

The result is a continuously updated OD matrix drawn as coloured polylines on a live map - all without a single camera frame or tap-off event.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LAYER 1 - DUMB EDGE                         │
│                                                                 │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │  Pi Zero 2W      │          │  Pi Zero 2W      │            │
│  │  (FRONT node)    │          │  (REAR node)     │            │
│  │                  │          │                  │            │
│  │ edge_sniffer.py  │          │ edge_sniffer.py  │            │
│  │  ble_sniffer.py  │          │  ble_sniffer.py  │            │
│  │ data_uploader.py │          │ data_uploader.py │            │
│  └────────┬─────────┘          └────────┬─────────┘            │
│           │  POST /api/ingest (JSON)     │                      │
│           │  every 10 seconds            │                      │
└───────────┼──────────────────────────────┼──────────────────────┘
            │                              │
            └──────────────┬───────────────┘
                           │  Mobile Hotspot
┌──────────────────────────▼───────────────────────────────────────┐
│                     LAYER 2 - SMART CORE                         │
│                                                                  │
│   FastAPI + SQLite (main.py)                                     │
│                                                                  │
│   ┌─────────────────────┐    ┌────────────────────────────────┐ │
│   │  POST /api/ingest   │    │  Async GTFS-RT Poller          │ │
│   │  - Validates payload│    │  - Polls DRT VehiclePositions  │ │
│   │  - Writes to SQLite │    │    every 15 seconds            │ │
│   └─────────────────────┘    │  - Stores GPS as "Flight Data  │ │
│                               │    Recorder" in SQLite         │ │
│   ┌─────────────────────┐    └────────────────────────────────┘ │
│   │  GET /api/matrix    │                                        │
│   │  - Reads last 2 hrs │    Signal differential math:          │
│   │  - Calculates OD    │                                        │
│   │  - Enriches with GPS│    Δ = RSSI_Front - RSSI_Rear         │
│   └─────────────────────┘                                        │
└──────────────────────────────────────────────────────────────────┘
                           │  JSON polling
┌──────────────────────────▼───────────────────────────────────────┐
│                  LAYER 3 - OPERATOR DASHBOARD                    │
│                                                                  │
│   index.html - Vanilla JS + Leaflet.js                           │
│   - Polls /api/matrix periodically                               │
│   - Draws green-to-red polylines for each passenger journey      │
└──────────────────────────────────────────────────────────────────┘
```

### The Signal Differential

Boarding and alighting doors are determined by comparing the average RSSI measured at each node in a 15-second window around first and last contact:

$$\Delta = RSSI_{Front} - RSSI_{Rear}$$

- $\Delta > 0$ - passenger is closer to the **Front** sensor
- $\Delta < 0$ - passenger is closer to the **Rear** sensor

### The "Time Travel Problem" and the GTFS Flight Data Recorder

There is a fundamental challenge: the system must wait **120 seconds** of silence before it can confirm that a passenger has alighted (distinguishing a genuine alight from a momentary signal dropout). By that time, the bus has moved on.

To solve this, an **async background task** polls the live [DRT GTFS-Realtime](https://drtonline.durhamregiontransit.com/gtfsrealtime/VehiclePositions) protobuf feed every 15 seconds and writes each GPS fix to a `bus_location_logs` table in SQLite. When the 120-second alighting timeout fires, the system queries this historical table to retrieve the GPS coordinates at the exact moment the passenger was last seen - not where the bus is right now.

---

## Repository Structure

```
drt-sentinal/
├── main.py                  # FastAPI backend - ingestion, OD matrix, GTFS poller
├── gtfs_scanner.py          # Standalone GTFS-RT diagnostic utility
├── index.html               # Operator dashboard (Leaflet.js)
├── requirements.txt         # Python backend dependencies
└── edge_nodes/
    ├── edge_sniffer.py      # Wi-Fi probe request capture (monitor mode)
    ├── ble_sniffer.py       # BLE advertisement capture
    ├── data_uploader.py     # Batches CSV rows and POSTs to backend
    └── enable_monitor_mode.sh  # Sets Alfa adapter into monitor mode
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Edge Hardware** | Raspberry Pi Zero 2W, Alfa AWUS036ACH Wi-Fi adapter |
| **Edge Software** | Python 3.11, Scapy (Wi-Fi sniff), Bleak (BLE scan) |
| **Backend** | Python 3.11, FastAPI, Uvicorn, SQLAlchemy, Pydantic |
| **Database** | SQLite |
| **GTFS Integration** | `gtfs-realtime-bindings`, `requests`, protobuf |
| **Frontend** | Vanilla JS, HTML5, CSS3, Leaflet.js |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Two Raspberry Pi Zero 2W units (or any Linux SBC) with Alfa AWUS036ACH adapters for production use
- A valid DRT GTFS-Realtime API key (obtain from Durham Region Transit)
- A mobile hotspot shared between the Pis and the backend host

---

### Step 1 - Clone the Repo and Create a Virtual Environment

```bash
git clone https://github.com/Sanyam-bot/drt-sentinal.git
cd drt-sentinal
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

---

### Step 2 - Install Backend Dependencies

```bash
pip install fastapi uvicorn sqlalchemy gtfs-realtime-bindings requests
```

Or install everything from the lockfile:

```bash
pip install -r requirements.txt
```

---

### Step 3 - Configure the Backend

Open **`main.py`** and update the two runtime constants near the top of the file:

```python
# main.py

ACTIVE_FLEET_ID = "8547"   # Change to the fleet/vehicle number of your target bus
DRT_API_KEY = os.getenv("DRT_API_KEY", "")
```

**Recommended** - set the API key via an environment variable rather than hardcoding it:

```bash
export DRT_API_KEY="your_drt_api_key_here"
```

Or create a `.env` file in the project root (the app uses `python-dotenv`):

```
DRT_API_KEY=your_drt_api_key_here
```

> **Note:** If `DRT_API_KEY` is left empty the backend will still start and ingest data, but the GTFS-RT poller will receive `401` responses and GPS enrichment will be unavailable.

---

### Step 4 - Start the Backend Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://<your-host-ip>:8000`. Visit `http://localhost:8000/docs` for the auto-generated Swagger UI.

| Endpoint | Method | Description |
|---|---|---|
| `/api/ingest` | `POST` | Accepts a JSON array of telemetry payloads from edge nodes |
| `/api/matrix` | `GET` | Returns the current OD matrix enriched with GPS coordinates |
| `/docs` | `GET` | Interactive Swagger UI |

---

### Step 5 - Configure and Run the Edge Nodes

On each Raspberry Pi:

**5a. Enable monitor mode on the Alfa adapter:**

```bash
cd edge_nodes
sudo bash enable_monitor_mode.sh
```

**5b. Update the backend IP in `data_uploader.py`:**

```python
# edge_nodes/data_uploader.py

WINDOWS_HOST_IP = "10.32.194.25"   # Replace with the IP of the machine running uvicorn
```

**5c. Start the sniffers and uploader (each in a separate terminal or `tmux` pane):**

```bash
# Terminal 1 - Wi-Fi sniffer (requires root)
sudo python3 edge_sniffer.py

# Terminal 2 - BLE sniffer
python3 ble_sniffer.py

# Terminal 3 - Uploader (reads CSVs and POSTs to backend every 10 s)
python3 data_uploader.py
```

Each node (Front and Rear) runs an identical set of scripts. The `node_location` field (`"Front"` or `"Rear"`) in the CSV identifies which node captured each reading.

> **RSSI filter:** Only signals stronger than **-85 dBm** are recorded to reduce noise from distant devices.

---

### Step 6 - Open the Dashboard

Open **`index.html`** directly in any modern web browser:

```
File > Open File > index.html
```

Or serve it from a simple HTTP server so Leaflet assets load correctly:

```bash
python3 -m http.server 3000
# then open http://localhost:3000
```

The dashboard will begin polling `/api/matrix` and rendering passenger journey polylines on the map. Colour transitions from **green** (boarding point) to **red** (alighting point).

---

## Future Roadmap

| Feature | Description |
|---|---|
| **Edge deduplication** | Deduplicate repeated probe bursts from the same MAC at the edge node level before uploading, reducing hotspot bandwidth usage by an estimated 60-80% |
| **Predictive ML crowding models** | Train a time-series model (e.g., LightGBM or LSTM) on historical OD matrices to forecast crowding levels by route segment and time of day |
| **Multi-bus fleet support** | Extend `ACTIVE_FLEET_ID` to a list and correlate telemetry batches to vehicles via the uploader's source IP or a configurable node ID |
| **Tap-on correlation** | Cross-reference anonymised OD flows with Presto smart card tap-on data (where available) to validate door-assignment accuracy |
| **Persistent deployment** | Package the backend as a `systemd` service and edge scripts as auto-start services for unattended operation |

---

## Privacy and Ethics

Transit Sentinel processes **MAC addresses only in hashed form**. Raw MAC addresses are never stored or transmitted. Modern smartphones randomise probe-request MAC addresses per session, so the system cannot track individuals across trips. The data is used solely for aggregate flow analysis by the transit operator.

---

## License

This project was built as a hackathon prototype. See [LICENSE](LICENSE) for details.
