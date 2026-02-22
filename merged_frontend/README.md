# Merged Accelerometer BPM + Crossfader Frontend

This folder is a **new merged frontend** that keeps your original code untouched.

It combines:
- BPM from the accelerometer API (`/tempo_mood`)
- Track selection by BPM
- WebSocket commands to the crossfader player
- A Streamlit UI showing:
  - raw current BPM from accelerometer
  - current playing BPM/song
  - incoming (next) BPM/song

## Run locally on your Mac

From repository root:

1. Install deps (in your venv):
   ```bash
   pip install streamlit fastapi uvicorn websockets requests
   ```

2. Start accelerometer tempo API:
   ```bash
   uvicorn --app-dir . api_endpoint.algo:app --reload --port 8000
   ```

   If you are already inside `merged_frontend/`, use:
   ```bash
   uvicorn --app-dir .. api_endpoint.algo:app --reload --port 8000
   ```

3. Start merged player server:
   ```bash
   uvicorn merged_frontend.player_server:app --reload --port 8502
   ```

4. Open player page and click **Start / Resume** once:
   - http://127.0.0.1:8502/player

5. Start merged Streamlit frontend:
   ```bash
   streamlit run merged_frontend/streamlit_merged_app.py
   ```

## Notes
- The app looks for music in `merged_frontend/music` first.
- If that folder does not exist, it automatically falls back to `crossfade/music`.
- BPM is normalized to 50–145 in 5 BPM increments to match your track naming convention.
