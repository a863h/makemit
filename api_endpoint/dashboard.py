"""
MOVICAL — Motion-to-Music Dashboard

Connects to the FastAPI backend which does the actual
acceleration processing and zero-crossing BPM detection.

The backend exposes:
    GET /tempo_mood → {"tempo": 120.5, "mood": "HAPPY"}

Run backend:  uvicorn main:app --reload --port 8000
Run dashboard: streamlit run app.py

Dependencies: pip3 install streamlit pandas requests
"""

import streamlit as st
import time
import requests
import random
from datetime import datetime

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Movical",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CONFIG — Point to your FastAPI backend
# ============================================================

BACKEND_URL = "http://172.20.10.5:8000"

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background: #0a0a0f;
        font-family: 'Outfit', sans-serif;
    }
    
    .movical-title {
        font-family: 'Outfit', sans-serif;
        font-size: 48px;
        font-weight: 800;
        letter-spacing: -1.5px;
        margin-bottom: 0;
    }
    
    .movical-subtitle {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        color: #7a7a8e;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    
    .metric-card {
        background: #12121a;
        border: 1px solid #1e1e2e;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 12px;
    }
    
    .metric-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 2px;
        color: #7a7a8e;
        margin-bottom: 8px;
    }
    
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 36px;
        font-weight: 800;
        letter-spacing: -1px;
        line-height: 1.1;
    }
    
    .metric-unit {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #4a4a5e;
    }
    
    .song-card {
        background: #12121a;
        border: 1px solid #1e1e2e;
        border-radius: 16px;
        padding: 28px;
        margin-bottom: 12px;
    }
    
    .song-detail {
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        color: #7a7a8e;
        margin: 4px 0;
    }
    
    .notes-display {
        font-family: 'JetBrains Mono', monospace;
        font-size: 20px;
        letter-spacing: 6px;
        padding: 12px 0;
    }
    
    .theory-box {
        background: #12121a;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0;
    }
    
    .tempo-display {
        font-family: 'JetBrains Mono', monospace;
        font-size: 80px;
        font-weight: 800;
        letter-spacing: -4px;
        line-height: 1;
    }
    
    .tempo-unit {
        font-family: 'JetBrains Mono', monospace;
        font-size: 18px;
        color: #7a7a8e;
        letter-spacing: 3px;
    }
    
    .connection-badge {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        padding: 4px 12px;
        border-radius: 20px;
        display: inline-block;
    }
    
    .intensity-bar-bg {
        background: #1e1e2e;
        border-radius: 8px;
        height: 12px;
        margin-top: 8px;
        overflow: hidden;
    }
    
    .intensity-bar-fill {
        height: 100%;
        border-radius: 8px;
        transition: width 0.5s ease;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# MUSIC THEORY — Maps BPM ranges to keys and characteristics
# ============================================================

# Each entry covers a BPM range and its musical characteristics
# BPM thresholds match the backend's mood classifier
MUSIC_MAP = {
    "CALM": {
        "bpm_range": "40-70",
        "keys": [
            {"key": "C Major", "notes": ["C", "D", "E", "F", "G", "A", "B"], "color": "#4A90D9"},
            {"key": "G Major", "notes": ["G", "A", "B", "C", "D", "E", "F#"], "color": "#5BA0E0"},
            {"key": "A Minor", "notes": ["A", "B", "C", "D", "E", "F", "G"], "color": "#6B7CB4"},
        ],
        "genre": "Ambient, Lo-fi, Soft Piano",
        "dynamics": "Soft (pp - p)",
        "energy": "Minimal",
        "description": "Barely moving — music should breathe slow, like resting",
        "chord_progression": "I - V - vi - IV",
        "color": "#4A90D9",
        "emoji": "☁️",
        "example_songs": ["Weightless - Marconi Union", "Clair de Lune - Debussy"]
    },
    "NEUTRAL": {
        "bpm_range": "70-100",
        "keys": [
            {"key": "F Major", "notes": ["F", "G", "A", "Bb", "C", "D", "E"], "color": "#6FC41E"},
            {"key": "D Major", "notes": ["D", "E", "F#", "G", "A", "B", "C#"], "color": "#7ED321"},
            {"key": "Bb Major", "notes": ["Bb", "C", "D", "Eb", "F", "G", "A"], "color": "#8AE036"},
        ],
        "genre": "Indie, Acoustic, Soft Pop",
        "dynamics": "Moderate (mp)",
        "energy": "Light",
        "description": "Gentle movement — music has a light pulse, easy groove",
        "chord_progression": "I - IV - V - I",
        "color": "#7ED321",
        "emoji": "🌿",
        "example_songs": ["Banana Pancakes - Jack Johnson", "Three Little Birds - Bob Marley"]
    },
    "HAPPY": {
        "bpm_range": "100-130",
        "keys": [
            {"key": "A Major", "notes": ["A", "B", "C#", "D", "E", "F#", "G#"], "color": "#F5C842"},
            {"key": "E Major", "notes": ["E", "F#", "G#", "A", "B", "C#", "D#"], "color": "#E8B830"},
            {"key": "D Major", "notes": ["D", "E", "F#", "G", "A", "B", "C#"], "color": "#DBB020"},
        ],
        "genre": "Pop, Funk, Dance, R&B",
        "dynamics": "Medium (mf)",
        "energy": "Medium",
        "description": "Steady rhythm detected — music locks into the beat",
        "chord_progression": "I - V - vi - IV",
        "color": "#F5C842",
        "emoji": "☀️",
        "example_songs": ["Uptown Funk - Bruno Mars", "Happy - Pharrell"]
    },
    "NERVOUS": {
        "bpm_range": "130-160",
        "keys": [
            {"key": "E Major", "notes": ["E", "F#", "G#", "A", "B", "C#", "D#"], "color": "#F5A623"},
            {"key": "B Minor", "notes": ["B", "C#", "D", "E", "F#", "G", "A"], "color": "#E89520"},
            {"key": "G Minor", "notes": ["G", "A", "Bb", "C", "D", "Eb", "F"], "color": "#D4911E"},
        ],
        "genre": "EDM, Rock, Hip-Hop, Trap",
        "dynamics": "Loud (f - ff)",
        "energy": "High",
        "description": "Fast cadence — music drives hard, pushes forward",
        "chord_progression": "i - VII - VI - V",
        "color": "#F5A623",
        "emoji": "⚡",
        "example_songs": ["Levels - Avicii", "HUMBLE - Kendrick Lamar"]
    },
    "ANGRY": {
        "bpm_range": "160-180",
        "keys": [
            {"key": "E Minor", "notes": ["E", "F#", "G", "A", "B", "C", "D"], "color": "#D0021B"},
            {"key": "D Minor", "notes": ["D", "E", "F", "G", "A", "Bb", "C"], "color": "#B80218"},
            {"key": "F# Minor", "notes": ["F#", "G#", "A", "B", "C#", "D", "E"], "color": "#9E0114"},
        ],
        "genre": "Hardcore, Metal, Hardstyle, Hard Trap",
        "dynamics": "Fortissimo (ff - fff)",
        "energy": "Maximum",
        "description": "Explosive movement — music matches with full force",
        "chord_progression": "i - iv - i - V",
        "color": "#D0021B",
        "emoji": "🔥",
        "example_songs": ["Till I Collapse - Eminem", "Through Fire and Flames - DragonForce"]
    }
}

# For intensity labels shown to user (not "emotions")
INTENSITY_LABELS = {
    "CALM": "Very Low",
    "NEUTRAL": "Low",
    "HAPPY": "Medium",
    "NERVOUS": "High",
    "ANGRY": "Maximum"
}


# ============================================================
# SESSION STATE
# ============================================================

if "history" not in st.session_state:
    st.session_state.history = []
if "last_key" not in st.session_state:
    st.session_state.last_key = None
if "last_mood" not in st.session_state:
    st.session_state.last_mood = None
if "backend_connected" not in st.session_state:
    st.session_state.backend_connected = False


# ============================================================
# POLL BACKEND
# ============================================================

tempo = None
mood_name = None

try:
    resp = requests.get(f"{BACKEND_URL}/tempo_mood", timeout=1)
    if resp.status_code == 200:
        data = resp.json()
        tempo = round(data["tempo"], 1)
        mood_name = data["mood"]
        st.session_state.backend_connected = True
except Exception:
    st.session_state.backend_connected = False


# ============================================================
# DETERMINE MUSIC CHARACTERISTICS
# ============================================================

if mood_name and mood_name in MUSIC_MAP:
    music = MUSIC_MAP[mood_name]
    
    # Keep same key if mood hasn't changed
    if st.session_state.last_mood != mood_name:
        key_info = random.choice(music["keys"])
        st.session_state.last_key = key_info
        st.session_state.last_mood = mood_name
    else:
        key_info = st.session_state.last_key
    
    # Add to history
    st.session_state.history.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "bpm": tempo,
        "intensity": mood_name
    })
    st.session_state.history = st.session_state.history[-60:]
else:
    music = MUSIC_MAP["CALM"]
    key_info = music["keys"][0]


# Get current color
current_color = music["color"] if mood_name else "#4A90D9"


# ============================================================
# HEADER
# ============================================================

col_title, col_status = st.columns([3, 2])
with col_title:
    st.markdown(f'<p class="movical-title" style="color: {current_color};">Movical</p>', unsafe_allow_html=True)
    st.markdown('<p class="movical-subtitle">motion → music &nbsp;|&nbsp; zero-crossing cadence engine</p>', unsafe_allow_html=True)
with col_status:
    if st.session_state.backend_connected and tempo:
        badge_color = "#7ED321"
        badge_text = "ENGINE LIVE"
    else:
        badge_color = "#D0021B"
        badge_text = "BACKEND OFFLINE"
    
    st.markdown(f"""
    <div style="text-align: right; padding-top: 24px;">
        <span class="connection-badge" style="background: {badge_color}15; color: {badge_color}; border: 1px solid {badge_color}40;">
            ● {badge_text}
        </span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")


# ============================================================
# MAIN LAYOUT
# ============================================================

if tempo is None:
    # ---- WAITING STATE ----
    st.markdown(f"""
    <div style="text-align: center; padding: 60px 20px;">
        <div style="font-size: 80px; margin-bottom: 20px;">🎵</div>
        <div style="font-family: 'Outfit'; font-size: 28px; font-weight: 700; color: #f0f0f5; margin-bottom: 12px;">
            Waiting for Cadence Engine
        </div>
        <div style="font-family: 'JetBrains Mono'; font-size: 14px; color: #7a7a8e; max-width: 500px; margin: 0 auto; line-height: 1.8;">
            Start the FastAPI backend:<br><br>
            <code style="background: #1e1e2e; padding: 6px 14px; border-radius: 6px; color: #F5A623;">
                uvicorn main:app --reload --port 8000
            </code><br><br>
            Then connect ESP32 to start sending acceleration data to<br>
            <code style="background: #1e1e2e; padding: 4px 12px; border-radius: 6px; color: #7ED321;">
                POST /acc_data
            </code>
        </div>
    </div>
    """, unsafe_allow_html=True)

else:
    # ---- LIVE DATA ----
    
    left_col, mid_col, right_col = st.columns([1.2, 1.8, 1.5])
    
    # ---- LEFT: BPM + Intensity ----
    with left_col:
        # Big BPM display
        st.markdown(f"""
        <div class="metric-card" style="border-color: {current_color}40; text-align: center; padding: 32px 24px;">
            <div class="metric-label">Detected Tempo</div>
            <div class="tempo-display" style="color: {current_color};">{int(tempo)}</div>
            <div class="tempo-unit">BPM</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Intensity level
        intensity_pct = min(100, max(0, ((tempo - 40) / 140) * 100))
        st.markdown(f"""
        <div class="metric-card" style="border-color: {current_color}40;">
            <div class="metric-label">Movement Intensity</div>
            <div class="metric-value" style="color: {current_color};">{INTENSITY_LABELS.get(mood_name, "—")}</div>
            <div class="intensity-bar-bg">
                <div class="intensity-bar-fill" style="width: {intensity_pct}%; background: {current_color};"></div>
            </div>
            <div class="metric-unit" style="margin-top: 8px;">Cadence range: {music['bpm_range']} BPM</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Energy + Dynamics
        st.markdown(f"""
        <div class="metric-card">
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <div class="metric-label">Energy</div>
                    <div style="font-family: 'JetBrains Mono'; font-size: 18px; font-weight: 700; color: {current_color};">{music['energy']}</div>
                </div>
                <div style="text-align: right;">
                    <div class="metric-label">Dynamics</div>
                    <div style="font-family: 'JetBrains Mono'; font-size: 18px; font-weight: 700; color: {current_color};">{music['dynamics']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    
    # ---- MIDDLE: Key + Song Characteristics ----
    with mid_col:
        # Mood/Intensity display
        st.markdown(f"""
        <div class="song-card" style="border-color: {current_color}40; text-align: center;">
            <div style="font-size: 56px; margin-bottom: 8px;">{music['emoji']}</div>
            <div style="font-size: 14px; font-weight: 600; color: {current_color}; text-transform: uppercase; letter-spacing: 3px;">
                {INTENSITY_LABELS.get(mood_name, "—")} Intensity
            </div>
            <div style="font-family: 'JetBrains Mono'; font-size: 12px; color: #7a7a8e; margin-top: 8px;">
                {music['description']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Key recommendation
        st.markdown(f"""
        <div class="song-card" style="border-color: {key_info['color']}40;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <div class="metric-label">Recommended Key</div>
                    <div style="font-size: 34px; font-weight: 800; color: {key_info['color']}; margin: 8px 0;">
                        {key_info['key']}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div class="metric-label">Matched Tempo</div>
                    <div style="font-family: 'JetBrains Mono'; font-size: 30px; font-weight: 800; color: {key_info['color']};">
                        {int(tempo)}
                    </div>
                    <div style="font-family: 'JetBrains Mono'; font-size: 11px; color: #4a4a5e;">BPM</div>
                </div>
            </div>
            <div class="song-detail" style="margin-top: 16px;">Genre: {music['genre']}</div>
            <div class="song-detail">Progression: {music['chord_progression']}</div>
            <div class="song-detail">Songs:
                {"".join(f' {s} /' for s in music['example_songs']).rstrip(' /')}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    
    # ---- RIGHT: Scale Notes + How It Works ----
    with right_col:
        notes_str = "  ".join(key_info["notes"])
        st.markdown(f"""
        <div class="song-card" style="border-color: {key_info['color']}40;">
            <div class="metric-label">Scale Notes</div>
            <div class="notes-display" style="color: {key_info['color']};">
                {notes_str}
            </div>
            <div style="margin-top: 12px;">
                <div class="metric-label">Chord Progression</div>
                <div style="font-family: 'JetBrains Mono'; font-size: 26px; color: #f0f0f5; padding: 8px 0; letter-spacing: 3px;">
                    {music['chord_progression']}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="theory-box">
            <div class="metric-label">How It Works</div>
            <div style="font-size: 13px; color: #b0b0c0; margin-top: 8px; line-height: 1.8;">
                Your accelerometer signal crosses zero every time you take a step.
                The time between crossings = your body's cadence.<br><br>
                Right now: <strong style="color: {current_color};">{int(tempo)} BPM</strong> cadence detected
                → matched to <strong style="color: {key_info['color']};">{key_info['key']}</strong>
                at <strong style="color: {current_color};">{music['dynamics']}</strong> dynamics.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="theory-box">
            <div class="metric-label">Algorithm</div>
            <div style="font-family: 'JetBrains Mono'; font-size: 11px; color: #5a5a6e; margin-top: 8px; line-height: 1.8;">
                1. Read accel magnitude<br>
                2. Subtract running average (removes gravity)<br>
                3. Detect zero-crossings (each = one step)<br>
                4. Time between crossings → step frequency<br>
                5. Step frequency × 60 → BPM<br>
                6. BPM → key + tempo + dynamics
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    
    # ---- BPM HISTORY CHART ----
    st.markdown("---")
    st.markdown('<div class="metric-label" style="padding-left: 4px;">Tempo History</div>', unsafe_allow_html=True)
    
    if len(st.session_state.history) > 1:
        import pandas as pd
        chart_data = pd.DataFrame(st.session_state.history)
        chart_data = chart_data.set_index("time")
        st.line_chart(chart_data["bpm"], color=current_color, height=200)


# ============================================================
# INTENSITY REFERENCE (always shown)
# ============================================================

st.markdown("---")
st.markdown('<div class="metric-label" style="padding-left: 4px;">Cadence → Intensity → Key Reference</div>', unsafe_allow_html=True)

ref_cols = st.columns(5)
for i, (m_name, m_data) in enumerate(MUSIC_MAP.items()):
    with ref_cols[i]:
        keys_list = ", ".join([k["key"] for k in m_data["keys"]])
        is_active = mood_name == m_name
        border = f"border: 2px solid {m_data['color']}" if is_active else "border: 1px solid #1e1e2e"
        st.markdown(f"""
        <div style="background: #12121a; {border}; border-radius: 12px; padding: 14px; text-align: center;">
            <div style="font-size: 22px;">{m_data['emoji']}</div>
            <div style="font-size: 12px; font-weight: 700; color: {m_data['color']}; margin: 4px 0;">
                {INTENSITY_LABELS[m_name].upper()}
            </div>
            <div style="font-family: 'JetBrains Mono'; font-size: 13px; color: {m_data['color']}; font-weight: 700;">
                {m_data['bpm_range']}
            </div>
            <div style="font-family: 'JetBrains Mono'; font-size: 10px; color: #4a4a5e;">BPM</div>
            <div style="font-size: 10px; color: #5a5a6e; margin-top: 4px;">{keys_list}</div>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown("""
<div style="text-align: center; font-family: 'JetBrains Mono'; font-size: 11px; color: #3a3a4e; padding: 10px;">
    MOVICAL — Make MIT x Make Harvard Hackathon 2026 &nbsp;|&nbsp; Zero-Crossing Cadence Engine
</div>
""", unsafe_allow_html=True)


# ============================================================
# AUTO REFRESH
# ============================================================

time.sleep(1.5)
st.rerun()












