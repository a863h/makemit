from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st
import websockets

PLAYER_WS = "ws://127.0.0.1:8502/ws"

BASE_DIR = Path(__file__).parent
MUSIC_DIR = BASE_DIR / "music"

SUPPORTED_EXTS = (".mp3", ".wav", ".ogg", ".m4a")
BPM_MIN, BPM_MAX, BPM_STEP = 50, 145, 5

def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))

def round_to_step(n: int, step: int) -> int:
    return int(round(n / step) * step)

def normalize_bpm(raw: int) -> int:
    n = clamp(int(raw), BPM_MIN, BPM_MAX)
    n = round_to_step(n, BPM_STEP)
    return clamp(n, BPM_MIN, BPM_MAX)

def find_track_for_bpm(bpm: int) -> Path | None:
    if not MUSIC_DIR.exists():
        return None
    patterns = [f"{bpm} *", f"{bpm}-*", f"{bpm}_*", f"{bpm}.*"]
    candidates = []
    for pat in patterns:
        candidates.extend(MUSIC_DIR.glob(pat))
    candidates = sorted([p for p in candidates if p.suffix.lower() in SUPPORTED_EXTS])
    return candidates[0] if candidates else None

async def send_ws_command(payload: dict):
    msg = json.dumps(payload)
    async with websockets.connect(PLAYER_WS) as ws:
        await ws.send(msg)

def send_command(payload: dict):
    # Streamlit-safe runner
    try:
        asyncio.run(send_ws_command(payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(send_ws_command(payload))
        loop.close()

st.set_page_config(page_title="BPM Controller", layout="centered")
st.title("BPM Controller")
st.caption("Player: http://127.0.0.1:8502/player")

if "current_bpm" not in st.session_state:
    st.session_state.current_bpm = 60
if "current_track" not in st.session_state:
    st.session_state.current_track = None

if not MUSIC_DIR.exists():
    st.error(f"Missing music folder: {MUSIC_DIR}")
    st.stop()

st.subheader("Current (controller)")
st.write(f"**BPM:** {st.session_state.current_bpm}")
st.write(f"**Track:** `{st.session_state.current_track}`" if st.session_state.current_track else "**Track:** (none yet)")

with st.form("bpm_form"):
    typed = st.text_input("Enter new BPM (50–145, rounds to nearest 5)", value=str(st.session_state.current_bpm))
    submitted = st.form_submit_button("Set BPM")

if submitted:
    try:
        target = normalize_bpm(int(typed.strip()))
    except ValueError:
        st.error("Please enter a valid integer BPM.")
        st.stop()

    track = find_track_for_bpm(target)
    if not track:
        st.error(f"No file found starting with '{target}' in {MUSIC_DIR} (e.g. '{target} - name.mp3').")
        st.stop()

    payload = {"type": "set", "bpm": target, "track": track.name}

    try:
        send_command(payload)
    except Exception as e:
        st.error(f"Could not send command to player server at {PLAYER_WS}. Is uvicorn running?\n\nError: {e}")
        st.stop()

    st.session_state.current_bpm = target
    st.session_state.current_track = track.name
    st.success(f"Sent: {target} → `{track.name}` (player should crossfade)")