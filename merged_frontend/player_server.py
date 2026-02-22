from __future__ import annotations

import json
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

APP_HOST = "127.0.0.1"
APP_PORT = 8502

BASE_DIR = Path(__file__).resolve().parent
MUSIC_DIR = BASE_DIR / "music"
if not MUSIC_DIR.exists():
    MUSIC_DIR = BASE_DIR.parent / "crossfade" / "music"

app = FastAPI()
app.mount("/music", StaticFiles(directory=str(MUSIC_DIR), html=False), name="music")

clients: Set[WebSocket] = set()

PLAYER_HTML = f"""
<!doctype html>
<html>
<head><meta charset=\"utf-8\" /><title>Merged BPM Player</title></head>
<body style=\"font-family: system-ui; padding: 16px;\">
  <h2>Merged BPM Player</h2>
  <button id=\"startBtn\">Start / Resume</button>
  <div id=\"status\" style=\"margin: 10px 0; opacity: .8;\"></div>
  <div>Now playing: <code id=\"now\"></code></div>
  <div>Incoming: <code id=\"incoming\"></code></div>
  <audio id=\"deckA\" loop></audio>
  <audio id=\"deckB\" loop></audio>
  <script>
    const WS_URL = `ws://{APP_HOST}:{APP_PORT}/ws`;
    const deckA = document.getElementById("deckA");
    const deckB = document.getElementById("deckB");
    const nowEl = document.getElementById("now");
    const incomingEl = document.getElementById("incoming");
    const statusEl = document.getElementById("status");
    const startBtn = document.getElementById("startBtn");
    const FADE_MS = 1100;

    let active = "A";
    let hasUserGesture = false;

    function setStatus(msg) {{ statusEl.textContent = msg; }}
    function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}
    async function tryPlay(el) {{ try {{ await el.play(); return true; }} catch(e) {{ return false; }} }}
    function getActiveDeck() {{ return active === "A" ? deckA : deckB; }}
    function getInactiveDeck() {{ return active === "A" ? deckB : deckA; }}

    async function equalPowerFade(fromEl, toEl) {{
      const steps = 40;
      const stepMs = Math.max(10, Math.floor(FADE_MS / steps));
      toEl.volume = 0; fromEl.volume = 1;
      for (let i = 0; i <= steps; i++) {{
        const t = i / steps;
        fromEl.volume = Math.cos(t * Math.PI / 2);
        toEl.volume = Math.sin(t * Math.PI / 2);
        await sleep(stepMs);
      }}
      fromEl.volume = 0; toEl.volume = 1;
    }}

    startBtn.addEventListener("click", async () => {{
      hasUserGesture = true;
      const activeEl = getActiveDeck();
      if (activeEl.src) await tryPlay(activeEl);
    }});

    async function loadInitial(url, label) {{
      const el = getActiveDeck();
      el.src = url; el.currentTime = 0; el.volume = 1;
      nowEl.textContent = label;
      if (!hasUserGesture) {{ setStatus("Click Start / Resume once to enable audio."); return; }}
      const ok = await tryPlay(el);
      setStatus(ok ? "Playing" : "Playback blocked");
    }}

    async function crossfadeTo(url, label) {{
      incomingEl.textContent = label;
      if (!hasUserGesture) {{ setStatus("Click Start / Resume once to enable audio."); return; }}
      const fromEl = getActiveDeck();
      const toEl = getInactiveDeck();
      toEl.src = url; toEl.currentTime = 0; toEl.volume = 0;
      const ok = await tryPlay(toEl);
      if (!ok) {{ setStatus("Playback blocked"); return; }}
      setStatus("Crossfading...");
      await equalPowerFade(fromEl, toEl);
      fromEl.pause();
      active = (active === "A") ? "B" : "A";
      nowEl.textContent = label;
      incomingEl.textContent = "";
      setStatus("Playing");
    }}

    function connect() {{
      const ws = new WebSocket(WS_URL);
      ws.onmessage = async (evt) => {{
        const msg = JSON.parse(evt.data);
        if (msg.type !== "set") return;
        const label = `${{msg.bpm}} — ${{msg.track}}`;
        const url = `/music/${{encodeURIComponent(msg.track)}}`;
        if (!getActiveDeck().src) await loadInitial(url, label);
        else await crossfadeTo(url, label);
      }};
      ws.onopen = () => setStatus("Connected");
      ws.onclose = () => {{ setStatus("Disconnected. Reconnecting..."); setTimeout(connect, 600); }};
    }}

    connect();
  </script>
</body>
</html>
"""


@app.get("/")
def root():
    return RedirectResponse(url="/player")


@app.get("/player", response_class=HTMLResponse)
def player() -> HTMLResponse:
    if not MUSIC_DIR.exists():
        return HTMLResponse(f"<h3>Missing music folder:</h3><p>{MUSIC_DIR}</p>", status_code=500)
    return HTMLResponse(PLAYER_HTML)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            dead = []
            for client in clients:
                try:
                    await client.send_text(text)
                except Exception:
                    dead.append(client)
            for client in dead:
                clients.discard(client)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)