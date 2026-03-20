import streamlit as st

def apply_custom_styles():
    st.markdown("""
        <style>
        * { font-family: Arial, sans-serif !important; }

        .compact-card {
            border: 1px solid #444;
            border-radius: 4px;
            padding: 4px 8px;
            margin: 2px 0px;
            background-color: #1e1e1e;
            line-height: 1.2;
        }

        .t-header { font-size: 1.1rem; font-weight: bold; color: white; }
        .t-ratio { font-size: 0.75rem; color: #888; margin-bottom: 4px; }
        .p-usd { color: #00FFFF; font-size: 0.95rem; font-weight: bold; }
        .p-ars { color: #00FF00; font-size: 0.95rem; font-weight: bold; }

        .rsi-normal { font-size: 0.85rem; color: #CCC; }

        .rsi-alert {
            background-color: #FF0000;
            color: white;
            padding: 2px 4px;
            border-radius: 2px;
            font-weight: bold;
            font-size: 0.85rem;
            display: inline-block;
        }

        .stButton > button {
            padding: 0px 2px !important;
            height: 20px !important;
            font-size: 10px !important;
        }
        </style>
    """, unsafe_allow_html=True)