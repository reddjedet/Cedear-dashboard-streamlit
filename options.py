import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st


@st.cache_data(ttl=600)
def get_options_data(tickers: tuple):
    """
    Descarga calls y puts de los próximos 30 días para cada ticker.
    Retorna:
      - df_long: DataFrame largo con una fila por contrato
      - prices:  dict {ticker: precio_actual_USD}
    """
    cutoff = datetime.today() + timedelta(days=30)
    all_rows = []
    prices = {}

    for ticker in tickers:
        try:
            tk = yf.Ticker(ticker)

            # Precio actual
            current_price = getattr(tk.fast_info, "last_price", None)
            if current_price:
                prices[ticker] = round(float(current_price), 2)

            expirations = tk.options
            if not expirations:
                continue

            for exp_str in expirations:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
                if exp_date > cutoff:
                    break

                chain = tk.option_chain(exp_str)

                for opt_type, df in [("Call", chain.calls), ("Put", chain.puts)]:
                    if df.empty:
                        continue

                    df = df.copy()
                    df["ticker"] = ticker
                    df["tipo"]   = opt_type
                    df["expira"] = exp_date.date()
                    df["dias"]   = (exp_date - datetime.today()).days + 1

                    df = df.rename(columns={
                        "volume":       "volumen",
                        "openInterest": "oi",
                        "inTheMoney":   "itm",
                    })

                    keep = ["ticker", "tipo", "expira", "dias", "strike", "volumen", "oi", "itm"]
                    df = df[[c for c in keep if c in df.columns]]

                    df["volumen"] = pd.to_numeric(df.get("volumen"), errors="coerce").fillna(0).astype(int)
                    df["oi"]      = pd.to_numeric(df.get("oi"),      errors="coerce").fillna(0).astype(int)

                    all_rows.append(df)

        except Exception as e:
            st.warning(f"Opciones {ticker}: {e}")
            continue

    if not all_rows:
        return pd.DataFrame(), prices

    result = pd.concat(all_rows, ignore_index=True)
    result = result.sort_values(["ticker", "expira", "strike"])
    return result, prices


def build_unified_chain(df_long: pd.DataFrame, ticker: str, expira,
                        precio_actual: float, rango_pct: float = None) -> pd.DataFrame:
    """
    Para un ticker + fecha, construye la tabla unificada:
      vol_call | oi_call | strike | oi_put | vol_put
    con columna 'es_precio' para marcar la fila más cercana al precio actual.
    Filtra opcionalmente por ±rango_pct% alrededor del precio actual.
    """
    sub = df_long[(df_long["ticker"] == ticker) & (df_long["expira"] == expira)]

    calls = sub[sub["tipo"] == "Call"][["strike", "volumen", "oi"]].rename(
        columns={"volumen": "vol_call", "oi": "oi_call"}
    )
    puts = sub[sub["tipo"] == "Put"][["strike", "volumen", "oi"]].rename(
        columns={"volumen": "vol_put", "oi": "oi_put"}
    )

    merged = pd.merge(calls, puts, on="strike", how="outer").sort_values("strike").reset_index(drop=True)
    merged = merged.fillna(0)

    for col in ["vol_call", "oi_call", "vol_put", "oi_put"]:
        merged[col] = merged[col].astype(int)

    # Marcar fila más cercana al precio actual
    if precio_actual and not merged.empty:
        idx_closest = (merged["strike"] - precio_actual).abs().idxmin()
        merged["es_precio"] = merged.index == idx_closest
    else:
        merged["es_precio"] = False

    # Filtro de rango ±%
    if rango_pct and precio_actual:
        low  = precio_actual * (1 - rango_pct / 100)
        high = precio_actual * (1 + rango_pct / 100)
        merged = merged[(merged["strike"] >= low) & (merged["strike"] <= high)].reset_index(drop=True)

    return merged


# ── Renderizado HTML ──────────────────────────────────────────────────────────

def fmt_num(val) -> str:
    """Formatea número entero con puntos de miles, o devuelve '—' si es cero."""
    if val == 0:
        return '<span style="color:#333">—</span>'
    return f"{int(val):,}".replace(",", ".")


def build_unified_html(chain_df: pd.DataFrame, precio_actual: float, orden_col: str) -> str:
    """
    Genera el HTML de la tabla unificada Call | Strike | Put.
    orden_col: 'Strike' | 'Volumen Call' | 'OI Call' | 'Volumen Put' | 'OI Put'
    """
    if chain_df.empty:
        return "<p style='color:#555;font-size:0.8rem'>Sin contratos en este rango.</p>"

    orden_map = {
        "Strike":       ("strike",   True),
        "Volumen Call": ("vol_call", False),
        "OI Call":      ("oi_call",  False),
        "Volumen Put":  ("vol_put",  False),
        "OI Put":       ("oi_put",   False),
    }
    sort_col, asc = orden_map.get(orden_col, ("strike", True))
    if sort_col in chain_df.columns:
        chain_df = chain_df.sort_values(sort_col, ascending=asc)

    rows_html = ""
    for _, r in chain_df.iterrows():
        is_precio = r.get("es_precio", False)
        if is_precio:
            row_style    = "background:#1a3a1a;border-top:2px solid #00FF00;border-bottom:2px solid #00FF00;"
            strike_style = "color:#00FF00;font-weight:bold;font-size:0.9rem;"
            precio_marker = ' <span style="color:#00FF00;font-size:0.7rem">◀ precio</span>'
        else:
            row_style    = "border-bottom:1px solid #222;"
            strike_style = "color:#00FFFF;font-weight:bold;"
            precio_marker = ""

        rows_html += f"""
        <tr style="{row_style}">
            <td style="padding:3px 8px;color:#4CAF50;text-align:right">{fmt_num(r["vol_call"])}</td>
            <td style="padding:3px 8px;color:#66BB6A;text-align:right">{fmt_num(r["oi_call"])}</td>
            <td style="padding:3px 10px;text-align:center;">
                <span style="{strike_style}">${r['strike']:.2f}</span>{precio_marker}
            </td>
            <td style="padding:3px 8px;color:#EF5350;text-align:left">{fmt_num(r["oi_put"])}</td>
            <td style="padding:3px 8px;color:#E57373;text-align:left">{fmt_num(r["vol_put"])}</td>
        </tr>
        """

    precio_label = f"Precio actual: ${precio_actual:.2f}" if precio_actual else ""

    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:0.82rem;font-family:Arial,sans-serif;">
        <thead>
            <tr style="border-bottom:1px solid #444;">
                <th colspan="2" style="padding:4px 8px;color:#4CAF50;text-align:right;border-right:1px solid #333">📈 CALL</th>
                <th style="padding:4px 10px;color:#888;text-align:center;font-size:0.75rem">{precio_label}</th>
                <th colspan="2" style="padding:4px 8px;color:#EF5350;text-align:left;border-left:1px solid #333">📉 PUT</th>
            </tr>
            <tr style="border-bottom:2px solid #333;color:#555;font-size:0.75rem;">
                <th style="padding:2px 8px;text-align:right">Vol</th>
                <th style="padding:2px 8px;text-align:right;border-right:1px solid #222">OI</th>
                <th style="padding:2px 10px;text-align:center">Strike</th>
                <th style="padding:2px 8px;text-align:left;border-left:1px solid #222">OI</th>
                <th style="padding:2px 8px;text-align:left">Vol</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """