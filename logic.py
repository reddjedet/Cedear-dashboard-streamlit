import yfinance as yf
import pandas as pd
import streamlit as st

CEDEAR_RATIOS = {
    "DE": 20.0, "MRK": 10.0, "LLY": 100.0, "NEM": 3.0, "MSTR": 20.0,
    "COST": 120.0, "PEP": 18.0, "CAT": 40.0, "GOOGL": 58.0, "MA": 66.0,
    "PM": 10.0, "AMAT": 30.0
}

def calculate_rsi(series, period=14):
    """RSI usando método de Wilder (correcto)."""
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

@st.cache_data(ttl=300)
def get_ticker_data(symbol):
    is_pam = symbol.upper() == "PAM"
    adr_symbol = symbol.upper()
    local_symbol = "PAMP.BA" if is_pam else f"{symbol.upper()}.BA"

    try:
        # 🔥 Intento 1: intradía
        df_adr = yf.download(adr_symbol, period="1mo", interval="1h", progress=False)

        # 🔥 Fallback automático si falla
        if df_adr.empty or df_adr["Close"].dropna().empty:
            df_adr = yf.download(adr_symbol, period="3mo", interval="1d", progress=False)

        if df_adr.empty:
            return None

        df_local = yf.download(local_symbol, period="5d", progress=False)

        # 🔥 Validación robusta de close_adr (evita bugs con MultiIndex de yfinance)
        close_adr = df_adr["Close"]
        if isinstance(close_adr, pd.DataFrame):
            close_adr = close_adr.iloc[:, 0]
        close_adr = close_adr.dropna()
        if len(close_adr) < 20:
            return None  # datos insuficientes para RSI confiable

        # Mismo tratamiento robusto para close_local
        close_local = None
        if not df_local.empty:
            _cl = df_local["Close"]
            if isinstance(_cl, pd.DataFrame):
                _cl = _cl.iloc[:, 0]
            _cl = _cl.dropna()
            if not _cl.empty:
                close_local = _cl

        current_adr = float(close_adr.iloc[-1])
        current_local = float(close_local.iloc[-1]) if close_local is not None else 0.0

        # RSI
        rsi_series = calculate_rsi(close_adr)
        current_rsi = float(rsi_series.dropna().iloc[-1])

        return {
            "adr": round(current_adr, 2),
            "local": round(current_local, 2),
            "rsi": round(current_rsi, 2),
            "is_pam": is_pam
        }

    except Exception as e:
        st.warning(f"{symbol}: {e}")
        return None