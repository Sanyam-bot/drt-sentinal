from collections import defaultdict
import time
from typing import Dict, Generator, List, Literal, Tuple

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Column, Index, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./drt_telemetry.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(Integer, nullable=False, index=True)
    node_location = Column(String, nullable=False)  # Front or Rear
    protocol = Column(String, nullable=False)
    pseudo_mac = Column(String, nullable=False)
    rssi = Column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_telemetry_logs_pseudo_mac_timestamp", "pseudo_mac", "timestamp"),
    )


class TelemetryPayload(BaseModel):
    timestamp: int
    node_location: Literal["Front", "Rear"]
    protocol: str
    pseudo_mac: str
    rssi: int


app = FastAPI(title="DRT Sentinel Ingestion API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def clean_telemetry_data(raw_data: List[TelemetryLog]) -> Dict[str, Dict[str, List[Tuple[int, int]]]]:
    passenger_tracks: Dict[str, Dict[str, List[Tuple[int, int]]]] = defaultdict(
        lambda: {"Front": [], "Rear": []}
    )

    for ping in raw_data:
        mac = ping.pseudo_mac
        if ping.node_location == "Front":
            passenger_tracks[mac]["Front"].append((ping.timestamp, ping.rssi))
        elif ping.node_location == "Rear":
            passenger_tracks[mac]["Rear"].append((ping.timestamp, ping.rssi))

    for track in passenger_tracks.values():
        track["Front"].sort(key=lambda item: item[0])
        track["Rear"].sort(key=lambda item: item[0])

    return passenger_tracks


def get_pings_between(
    pings: List[Tuple[int, int]],
    start_time: int,
    end_time: int,
) -> List[Tuple[int, int]]:
    return [ping for ping in pings if start_time <= ping[0] <= end_time]


def average_rssi(pings: List[Tuple[int, int]]) -> float:
    if not pings:
        return float("-inf")
    return sum(rssi for _, rssi in pings) / len(pings)


def calculate_od_matrix(
    passenger_tracks: Dict[str, Dict[str, List[Tuple[int, int]]]],
) -> List[dict]:
    valid_journeys: List[dict] = []

    timeout_seconds = 120
    window_seconds = 15
    current_time = int(time.time())

    for mac, track in passenger_tracks.items():
        front_track = track["Front"]
        rear_track = track["Rear"]

        if not front_track and not rear_track:
            continue

        last_candidates = []
        if front_track:
            last_candidates.append(front_track[-1][0])
        if rear_track:
            last_candidates.append(rear_track[-1][0])

        last_seen_time = max(last_candidates)
        time_since_last_seen = current_time - last_seen_time

        if time_since_last_seen < timeout_seconds:
            continue

        first_candidates = []
        if front_track:
            first_candidates.append(front_track[0][0])
        if rear_track:
            first_candidates.append(rear_track[0][0])

        first_seen_time = min(first_candidates)

        front_boarding_pings = get_pings_between(
            front_track,
            first_seen_time,
            first_seen_time + window_seconds,
        )
        rear_boarding_pings = get_pings_between(
            rear_track,
            first_seen_time,
            first_seen_time + window_seconds,
        )

        avg_front_start = average_rssi(front_boarding_pings)
        avg_rear_start = average_rssi(rear_boarding_pings)

        boarding_door = "Unknown"
        if avg_front_start > avg_rear_start:
            boarding_door = "Front"
        elif avg_rear_start > avg_front_start:
            boarding_door = "Rear"

        front_alighting_pings = get_pings_between(
            front_track,
            last_seen_time - window_seconds,
            last_seen_time,
        )
        rear_alighting_pings = get_pings_between(
            rear_track,
            last_seen_time - window_seconds,
            last_seen_time,
        )

        avg_front_end = average_rssi(front_alighting_pings)
        avg_rear_end = average_rssi(rear_alighting_pings)

        alighting_door = "Unknown"
        if avg_rear_end > avg_front_end:
            alighting_door = "Rear"
        elif avg_front_end > avg_rear_end:
            alighting_door = "Front"

        valid_journeys.append(
            {
                "mac_hash": mac,
                "boarded_at": boarding_door,
                "boarding_time": first_seen_time,
                "alighted_at": alighting_door,
                "alighting_time": last_seen_time,
            }
        )

    return valid_journeys


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.post("/api/ingest")
def ingest(payloads: List[TelemetryPayload], db: Session = Depends(get_db)) -> dict:
    if not payloads:
        raise HTTPException(status_code=400, detail="Payload list cannot be empty")

    rows = [
        TelemetryLog(
            timestamp=item.timestamp,
            node_location=item.node_location,
            protocol=item.protocol,
            pseudo_mac=item.pseudo_mac,
            rssi=item.rssi,
        )
        for item in payloads
    ]

    db.bulk_save_objects(rows)
    db.commit()

    return {"inserted": len(rows)}


@app.get("/api/matrix")
def matrix(db: Session = Depends(get_db)) -> List[dict]:
    now = int(time.time())
    two_hours_ago = now - (2 * 60 * 60)

    raw_data = (
        db.query(TelemetryLog)
        .filter(TelemetryLog.timestamp >= two_hours_ago)
        .order_by(TelemetryLog.pseudo_mac, TelemetryLog.timestamp)
        .all()
    )

    passenger_tracks = clean_telemetry_data(raw_data)
    return calculate_od_matrix(passenger_tracks)
