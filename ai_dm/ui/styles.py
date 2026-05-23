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
</style>
"""


def inject() -> None:
    """Injeta o CSS global no app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
