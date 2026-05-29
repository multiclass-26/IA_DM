"""CSS e estilos globais da UI."""

import streamlit as st

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap');

    .stApp {
        background-color: #0e0e12;
        color: #d4d4d8;
        font-family: 'Inter', sans-serif;
    }

    div[data-testid="stSidebar"] {
        background-color: #111117;
        border-right: 1px solid #27272a;
    }

    h1, h2, h3 {
        font-family: 'Crimson Text', serif !important;
        color: #f4f4f5 !important;
        letter-spacing: 0.02em;
    }

    .stChatMessage {
        background-color: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
    }

    .stButton > button {
        background-color: #27272a !important;
        color: #f4f4f5 !important;
        border: 1px solid #3f3f46 !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        background-color: #3f3f46 !important;
        border-color: #52525b !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #7c3aed !important;
        border-color: #7c3aed !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #6d28d9 !important;
    }

    .stProgress > div > div > div {
        background-color: #7c3aed !important;
    }

    hr {
        border-color: #27272a !important;
    }

    [data-testid="stMetricValue"] {
        color: #f4f4f5 !important;
    }
    [data-testid="stMetricDelta"] {
        color: #a78bfa !important;
    }

    .streamlit-expanderHeader {
        background-color: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 6px !important;
        color: #d4d4d8 !important;
    }

    .stTextInput > div > div > input,
    .stSelectbox > div > div {
        background-color: #18181b !important;
        border-color: #3f3f46 !important;
        color: #f4f4f5 !important;
    }

    .hp-bar-high { color: #4ade80; }
    .hp-bar-mid { color: #facc15; }
    .hp-bar-low { color: #ef4444; }

    .combat-shell {
        background: linear-gradient(180deg, rgba(24,24,27,0.95), rgba(15,15,20,0.98));
        border: 1px solid #2f2f39;
        border-radius: 16px;
        padding: 1rem 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
    }

    .combat-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .combat-header h2 {
        margin: 0.15rem 0 0.25rem !important;
        font-size: 1.9rem !important;
    }

    .combat-header p,
    .combat-card-meta {
        margin: 0;
        color: #b3b3c4;
    }

    .combat-eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.72rem;
        color: #a78bfa;
    }

    .combat-badge,
    .combat-card-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.35rem 0.65rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        background: #27272a;
        color: #f4f4f5;
        border: 1px solid #3f3f46;
    }

    .combat-badge-danger {
        background: rgba(127, 29, 29, 0.35);
        border-color: rgba(248, 113, 113, 0.45);
        color: #fecaca;
    }

    .combat-stat-card,
    .combat-enemy-card,
    .combat-summary-card,
    .combat-log-item {
        background: rgba(24, 24, 27, 0.95);
        border: 1px solid #2f2f39;
        border-radius: 14px;
    }

    .combat-stat-card {
        padding: 0.85rem 1rem;
        min-height: 92px;
    }

    .combat-stat-card span {
        display: block;
        font-size: 0.78rem;
        color: #a1a1aa;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.35rem;
    }

    .combat-stat-card strong {
        font-size: 1.4rem;
        color: #fafafa;
    }

    .combat-enemy-card {
        padding: 0.9rem 1rem;
        margin-bottom: 0.45rem;
        min-height: 110px;
    }

    .combat-enemy-card-selected {
        border-color: #a78bfa;
        box-shadow: 0 0 0 1px rgba(167, 139, 250, 0.35);
        background: linear-gradient(180deg, rgba(60, 41, 102, 0.28), rgba(24, 24, 27, 0.95));
    }

    .combat-card-title {
        font-family: 'Crimson Text', serif;
        font-size: 1.3rem;
        color: #fafafa;
        margin-bottom: 0.2rem;
    }

    .combat-card-badge {
        margin-top: 0.65rem;
    }

    .combat-action-group-label {
        margin: 0.9rem 0 0.45rem;
        font-size: 0.82rem;
        color: #a1a1aa;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .combat-summary-card {
        padding: 0.9rem 1rem;
        margin-bottom: 0.9rem;
    }

    .combat-log-item {
        padding: 0.75rem 0.9rem;
        margin-bottom: 0.5rem;
        color: #d4d4d8;
    }
</style>
"""


def inject() -> None:
    """Injeta o CSS global no app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
