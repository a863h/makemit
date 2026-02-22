from __future__ import annotations

import json
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

APP_HOST = "127.0.0.1"
APP_PORT = 8502

BASE_DIR = Path(__file__).parent
MUSIC_DIR = BASE_DIR / "music"  # <-- your directory name

app = FastAPI()

# Serve audio files at: http://127.0.0.1:8502/music/<filename>
app.mount("/music", StaticFiles(directory=str(MUSIC_DIR), html=False), name="music")

# All connected WS clients (player page + controllers)
clients: Set[WebSocket] = set()

PLAYER_HTML = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Persistent BPM Player</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 16px; }}
    button {{ padding: 8px 12px; border-radius: 10px; border: 1px solid #ccc; background:#fff; cursor:pointer; }}
    .row {{ display:flex; gap:10px; align-items:center; margin-top: 10px; }}
    .muted {{ opacity: .85; font-size: 13px; }}
    code {{ background: #f6f6f6; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h2>Persistent BPM Player</h2>

  <div class="row">
    <button id="startBtn">Start / Resume</button>
    <div id="status" class="muted"></div>
  </div>

  <div class="muted" style="margin-top:12px;">
    Now playing: <code id="now"></code><br/>
    Incoming: <code id="incoming"></code>
  </div>

  <audio id="deckA" loop></audio>
  <audio id="deckB" loop></audio>

  <script>
    const WS_URL = `ws://{APP_HOST}:{APP_PORT}/ws`;
    const FADE_MS = 1100;

    const deckA = document.getElementById("deckA");
    const deckB = document.getElementById("deckB");
    const startBtn = document.getElementById("startBtn");
    const statusEl = document.getElementById("status");
    const nowEl = document.getElementById("now");
    const incomingEl = document.getElementById("incoming");

    let active = "A";
    let hasUserGesture = false;

    function setStatus(msg) {{ statusEl.textContent = msg; }}
    function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

    async function tryPlay(el) {{
      try {{ await el.play(); return true; }} catch(e) {{ return false; }}
    }}

    function getActiveDeck() {{ return active === "A" ? deckA : deckB; }}
    function getInactiveDeck() {{ return active === "A" ? deckB : deckA; }}

    async function equalPowerFade(fromEl, toEl) {{
      const steps = 40;
      const stepMs = Math.max(10, Math.floor(FADE_MS / steps));
      toEl.volume = 0.0;
      fromEl.volume = 1.0;

      for (let i = 0; i <= steps; i++) {{
        const t = i / steps;
        fromEl.volume = Math.cos(t * Math.PI / 2);
        toEl.volume   = Math.sin(t * Math.PI / 2);
        await sleep(stepMs);
      }}
      fromEl.volume = 0;
      toEl.volume = 1;
    }}

    async function ensureStarted() {{
      const el = getActiveDeck();
      if (!el.src) {{
        setStatus("Waiting for first BPM command...");
        return;
      }}
      const ok = await tryPlay(el);
      setStatus(ok ? "Playing (looping)." : "Playback blocked. Click Start / Resume again.");
    }}

    startBtn.addEventListener("click", async () => {{
      hasUserGesture = true;
      await ensureStarted();
    }});

    async function loadInitial(url, label) {{
      const el = getActiveDeck();
      el.src = url;
      el.currentTime = 0;
      el.volume = 1.0;
      nowEl.textContent = label;
      incomingEl.textContent = "";

      if (!hasUserGesture) {{
        setStatus("Click Start / Resume once to enable audio.");
        return;
      }}

      const ok = await tryPlay(el);
      setStatus(ok ? "Playing (looping)." : "Playback blocked. Click Start / Resume.");
    }}

    async function crossfadeTo(url, label) {{
      incomingEl.textContent = label;

      if (!hasUserGesture) {{
        setStatus("Click Start / Resume once to enable audio.");
        return;
      }}

      const fromEl = getActiveDeck();
      const toEl = getInactiveDeck();

      toEl.src = url;
      toEl.currentTime = 0;
      toEl.volume = 0.0;

      const ok = await tryPlay(toEl);
      if (!ok) {{
        setStatus("Playback blocked. Click Start / Resume.");
        return;
      }}

      setStatus("Crossfading...");
      await equalPowerFade(fromEl, toEl);

      fromEl.pause();
      fromEl.currentTime = 0;

      active = (active === "A") ? "B" : "A";
      nowEl.textContent = label;
      incomingEl.textContent = "";
      setStatus("Playing (looping).");
    }}

    let ws;

    function connect() {{
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {{
        setStatus("Connected. Waiting for commands...");
      }};

      ws.onclose = () => {{
        setStatus("Disconnected. Reconnecting...");
        setTimeout(connect, 600);
      }};

      ws.onmessage = async (evt) => {{
        try {{
          const msg = JSON.parse(evt.data);
          if (msg.type !== "set") return;

          const track = msg.track;
          const bpm = msg.bpm;

          const url = `/music/${{encodeURIComponent(track)}}`;
          const label = `${{bpm}} — ${{track}}`;

          if (!getActiveDeck().src) {{
            await loadInitial(url, label);
          }} else {{
            await crossfadeTo(url, label);
          }}
        }} catch (e) {{}}
      }};
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
        return HTMLResponse(
            f"<h3>Missing music folder:</h3><p>{MUSIC_DIR}</p>",
            status_code=500,
        )
    return HTMLResponse(PLAYER_HTML)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            # Any client can send a message (Streamlit controller does).
            # We broadcast it to ALL clients (including the player page).
            text = await websocket.receive_text()

            dead = []
            for c in clients:
                try:
                    await c.send_text(text)
                except Exception:
                    dead.append(c)
            for c in dead:
                clients.discard(c)

    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)