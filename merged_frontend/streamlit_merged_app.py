from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import streamlit as st
import websockets

# --- Endpoints ---
PLAYER_WS = os.getenv("PLAYER_WS", "ws://127.0.0.1:8502/ws")
TEMPO_API = os.getenv("TEMPO_API", "http://127.0.0.1:8000/tempo_mood")

# --- Track config ---
BASE_DIR = Path(__file__).resolve().parent
MUSIC_DIR = BASE_DIR / "music"
SUPPORTED_EXTS = (".mp3", ".wav", ".ogg", ".m4a")
BPM_MIN, BPM_MAX, BPM_STEP = 50, 145, 5


@dataclass
class TempoState:
    bpm: float
    mood: str
    accelerometer_connected: bool
    led_strip_connected: bool


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


def round_to_step(n: int, step: int) -> int:
    return int(round(n / step) * step)


def normalize_bpm(raw: float) -> int:
    n = clamp(int(round(raw)), BPM_MIN, BPM_MAX)
    n = round_to_step(n, BPM_STEP)
    return clamp(n, BPM_MIN, BPM_MAX)


def find_track_for_bpm(bpm: int) -> Path | None:
    if not MUSIC_DIR.exists():
        return None

    patterns = [f"{bpm} *", f"{bpm}-*", f"{bpm}_*", f"{bpm}.*"]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(MUSIC_DIR.glob(pattern))

    candidates = sorted([p for p in candidates if p.suffix.lower() in SUPPORTED_EXTS])
    return candidates[0] if candidates else None


def fetch_tempo() -> TempoState:
    response = requests.get(TEMPO_API, timeout=2)
    response.raise_for_status()
    payload = response.json()

    bpm = float(payload.get("tempo", 65))
    mood = str(payload.get("mood", "UNKNOWN"))
    devices = payload.get("devices", {})
    accelerometer_connected = bool(devices.get("accelerometer_connected", False))
    led_strip_connected = bool(devices.get("led_strip_connected", False))

    return TempoState(
        bpm=bpm,
        mood=mood,
        accelerometer_connected=accelerometer_connected,
        led_strip_connected=led_strip_connected,
    )


async def send_ws_command(payload: dict) -> None:
    async with websockets.connect(PLAYER_WS) as ws:
        await ws.send(json.dumps(payload))


def send_command(payload: dict) -> None:
    try:
        asyncio.run(send_ws_command(payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(send_ws_command(payload))
        loop.close()


def initialize_state() -> None:
    defaults = {
        "api_bpm": None,
        "api_mood": "UNKNOWN",
        "current_bpm": None,
        "current_track": None,
        "incoming_bpm": None,
        "incoming_track": None,
        "last_error": None,
        "last_updated": None,
        "auto_refresh": True,
        "refresh_seconds": 2,
        "accelerometer_connected": False,
        "led_strip_connected": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def update_from_accelerometer() -> None:
    try:
        tempo = fetch_tempo()
    except Exception as exc:
        st.session_state.last_error = f"Tempo API error: {exc}"
        return

    st.session_state.last_error = None
    st.session_state.api_bpm = tempo.bpm
    st.session_state.api_mood = tempo.mood
    st.session_state.accelerometer_connected = tempo.accelerometer_connected
    st.session_state.led_strip_connected = tempo.led_strip_connected
    st.session_state.last_updated = time.strftime("%H:%M:%S")

    target_bpm = normalize_bpm(tempo.bpm)
    target_track = find_track_for_bpm(target_bpm)

    st.session_state.incoming_bpm = target_bpm
    st.session_state.incoming_track = target_track.name if target_track else None

    if not target_track:
        st.session_state.last_error = (
            f"No track found for BPM {target_bpm}. Expected files like '{target_bpm} - name.mp3' in {MUSIC_DIR}."
        )
        return

    if (
        st.session_state.current_bpm == target_bpm
        and st.session_state.current_track == target_track.name
    ):
        return

    payload = {"type": "set", "bpm": target_bpm, "track": target_track.name}

    try:
        send_command(payload)
    except Exception as exc:
        st.session_state.last_error = f"Player WebSocket error: {exc}"
        return

    st.session_state.current_bpm = target_bpm
    st.session_state.current_track = target_track.name


def main() -> None:
    st.set_page_config(page_title="Merged BPM + Crossfader", layout="centered")
    initialize_state()

    st.title("Merged Accelerometer BPM + Crossfader")
    st.caption("Reads BPM from /tempo_mood, picks a matching track, and sends crossfade commands to /ws.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Refresh now"):
            update_from_accelerometer()
    with c2:
        st.session_state.auto_refresh = st.toggle("Auto refresh", value=st.session_state.auto_refresh)

    st.session_state.refresh_seconds = st.slider(
        "Auto refresh interval (seconds)", min_value=1, max_value=10, value=st.session_state.refresh_seconds
    )

    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_seconds)
        update_from_accelerometer()
        st.rerun()

    st.subheader("Accelerometer feed")
    st.write(f"**Current BPM (raw):** {st.session_state.api_bpm if st.session_state.api_bpm is not None else 'N/A'}")
    st.write(f"**Mood:** {st.session_state.api_mood}")
    st.write(f"**Last updated:** {st.session_state.last_updated or 'Never'}")

    st.subheader("ESP32 device status")
    st.write(
        f"**Accelerometer ESP32:** {'Connected' if st.session_state.accelerometer_connected else 'Disconnected'}"
    )
    st.write(
        f"**LED Strip ESP32:** {'Connected' if st.session_state.led_strip_connected else 'Disconnected'}"
    )

    st.subheader("Track transition state")
    st.write(f"**Current playing BPM:** {st.session_state.current_bpm if st.session_state.current_bpm is not None else 'N/A'}")
    st.write(f"**Current song:** {st.session_state.current_track or 'N/A'}")
    st.write(f"**Incoming BPM:** {st.session_state.incoming_bpm if st.session_state.incoming_bpm is not None else 'N/A'}")
    st.write(f"**Incoming song:** {st.session_state.incoming_track or 'N/A'}")

    if st.session_state.last_error:
        st.error(st.session_state.last_error)
    else:
        st.success("Connected and ready.")

    st.markdown(
        """
        ### Run dependencies
        1. Start cadence API from repo root: `uvicorn --app-dir . api_endpoint.algo:app --reload --port 8000`
           - If running from `merged_frontend/`: `uvicorn --app-dir .. api_endpoint.algo:app --reload --port 8000`
        2. Start player server from this folder: `uvicorn player_server:app --reload --port 8502`
        3. Open player page once: `http://127.0.0.1:8502/player` and click **Start / Resume**
        4. Run this frontend: `streamlit run streamlit_merged_app.py`
        """
    )


if __name__ == "__main__":
    main()
