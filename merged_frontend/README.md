# Merged Accelerometer BPM + Crossfader Frontend

This folder combines:
- BPM from the accelerometer API (`/tempo_mood`)
- Track selection by BPM
- WebSocket commands to the crossfader player
- A Streamlit UI for observing BPM and track transitions

## Why your `api_endpoint` import can fail

If you run from `merged_frontend/`, Python sometimes does not include the repo root on the import path in the way you expect (depends on shell, venv, and uvicorn invocation).

To avoid this, use **module mode** (`python -m uvicorn`) from repo root, or use the helper script below.

## Recommended startup (most reliable)

From repository root:

```bash
python -m uvicorn api_endpoint.algo:app --reload --port 8000
python -m uvicorn merged_frontend.player_server:app --reload --port 8502
python -m streamlit run merged_frontend/streamlit_merged_app.py
```

Open:
- Player page: http://127.0.0.1:8502/player (click **Start / Resume** once)
- Streamlit page: usually http://127.0.0.1:8501

## One-command startup

From repository root:

```bash
./merged_frontend/run_stack.sh
```

This starts all 3 services together and stops them together on Ctrl+C.

## If you insist on running from `merged_frontend/`

Use one of these:

```bash
# Option A: point uvicorn directly to the api folder
python -m uvicorn --app-dir ../api_endpoint algo:app --reload --port 8000

# Option B: set PYTHONPATH to repo root and keep package import
PYTHONPATH=.. python -m uvicorn api_endpoint.algo:app --reload --port 8000
```

## Hacky but practical multi-instance patterns

If you want independent test sessions:

```bash
# session 1
python -m uvicorn api_endpoint.algo:app --reload --port 8000
python -m uvicorn merged_frontend.player_server:app --reload --port 8502
python -m streamlit run merged_frontend/streamlit_merged_app.py --server.port 8501

# session 2
python -m uvicorn api_endpoint.algo:app --reload --port 8100
python -m uvicorn merged_frontend.player_server:app --reload --port 8602
TEMPO_API=http://127.0.0.1:8100/tempo_mood PLAYER_WS=ws://127.0.0.1:8602/ws \
python -m streamlit run merged_frontend/streamlit_merged_app.py --server.port 8601
```

> Note: for multi-instance routing, keep ports unique and point Streamlit to the matching API + player URLs.

## Music folder behavior

- Primary search path: `merged_frontend/music`
- Fallback search path: `crossfade/music`
- Expected filename style: `"<bpm> - <name>.mp3"` (BPM normalized 50–145 in steps of 5)
