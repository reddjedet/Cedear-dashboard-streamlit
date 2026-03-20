import io
import streamlit as st
import plotly.graph_objects as go

from logic import get_ticker_data, CEDEAR_RATIOS
from portfolio import PORTFOLIO_1, PORTFOLIO_2, calculate_portfolio
from options import get_options_data, build_unified_chain, build_unified_html
from valuation import (
    QUARTERS, EMPTY_QUARTER,
    parse_csv, export_csv, build_series, build_chart,
    build_verdict, render_verdict_html,
)

# ── Configuración ─────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Finanzas App")

st.markdown("""
<style>
* { font-family: Arial, sans-serif !important; }
.compact-card {
    border: 1px solid #444; border-radius: 4px;
    padding: 4px 8px; margin: 2px 0px;
    background-color: #1e1e1e; line-height: 1.2;
}
.t-header { font-size: 1.1rem; font-weight: bold; color: white; }
.t-ratio  { font-size: 0.75rem; color: #888; margin-bottom: 4px; }
.p-usd    { color: #00FFFF; font-size: 0.95rem; font-weight: bold; }
.p-ars    { color: #00FF00; font-size: 0.95rem; font-weight: bold; }
.rsi-normal { font-size: 0.85rem; color: #CCC; }
.rsi-alert  {
    background-color: #FF0000; color: white;
    padding: 2px 4px; border-radius: 2px;
    font-weight: bold; font-size: 0.85rem; display: inline-block;
}
.stButton > button { padding: 0px 2px !important; height: 20px !important; font-size: 10px !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state inicial ─────────────────────────────────────────────────────
if "tickers" not in st.session_state:
    st.session_state.tickers = [
        "DE", "MRK", "LLY", "NEM", "MSTR",
        "COST", "PEP", "PAM", "CAT", "GOOGL",
        "MA", "PM", "AMAT"
    ]
if "val_ticker" not in st.session_state:
    st.session_state.val_ticker = ""
    st.session_state.val_ticker_input = ""
if "val_data" not in st.session_state:
    st.session_state.val_data = {q: dict(EMPTY_QUARTER) for q in QUARTERS}
    # Inicializar keys de widgets para evitar conflicto value= vs session_state
    for _q in QUARTERS:
        st.session_state[f"val_price_{_q}"]  = ""
        st.session_state[f"val_shares_{_q}"] = ""
        st.session_state[f"val_ocf_{_q}"]    = ""
        st.session_state[f"val_bb_{_q}"]     = ""


# ── Helpers de render reutilizables ──────────────────────────────────────────
def render_portfolio_table(rows, total_ars):
    def rsi_badge(rsi):
        if rsi is None:
            return '<span style="color:#666">—</span>'
        alert = rsi >= 70 or rsi <= 30
        if alert:
            return f'<span style="background-color:#FF0000;color:white;padding:2px 4px;border-radius:2px;font-weight:bold;font-size:0.82rem;display:inline-block">RSI {rsi}</span>'
        return f'<span style="font-size:0.82rem;color:#CCC">RSI {rsi}</span>'

    def err_color(e):
        if e is None: return "#888"
        return "#00FF00" if abs(e) <= 1 else ("#FFA500" if abs(e) <= 3 else "#FF4444")

    def fmt_ars(v):
        return "—" if v is None else f"${v:,.0f}".replace(",", ".")

    rows_html = ""
    for r in rows:
        rows_html += f"""
        <tr>
            <td><b style="color:white">{r['ticker']}</b></td>
            <td style="color:#aaa">{r['weight_target']:.2f}%</td>
            <td style="color:#00FFFF">{r['qty_rounded'] or '—'}
                <span style="font-size:0.7rem;color:#555">{'(' + f"{r['qty_ideal']:.2f}" + ')' if r['qty_ideal'] else ''}</span>
            </td>
            <td style="color:#00FF00">{fmt_ars(r['cost_ars'])}</td>
            <td style="color:#ccc">{f"{r['weight_real']:.2f}%" if r['weight_real'] else '—'}</td>
            <td style="color:{err_color(r['error_pct'])}">{f"{r['error_pct']:+.2f}%" if r['error_pct'] is not None else '—'}</td>
            <td>{rsi_badge(r['rsi'])}</td>
        </tr>"""

    st.html(f"""
    <table style="width:100%;border-collapse:collapse;font-size:0.82rem;font-family:Arial,sans-serif;">
        <thead><tr style="border-bottom:1px solid #444;color:#888;text-align:left;">
            <th style="padding:4px 6px">Ticker</th><th style="padding:4px 6px">Peso obj.</th>
            <th style="padding:4px 6px">Cant. (ideal)</th><th style="padding:4px 6px">Costo ARS</th>
            <th style="padding:4px 6px">Peso real</th><th style="padding:4px 6px">Error</th>
            <th style="padding:4px 6px">RSI</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
        <tfoot><tr style="border-top:1px solid #444;">
            <td colspan="3" style="padding:6px;color:#888;font-size:0.8rem;">Total portfolio</td>
            <td colspan="4" style="padding:6px;color:#FFD700;font-weight:bold;font-size:0.95rem;">{fmt_ars(total_ars)}</td>
        </tr></tfoot>
    </table>""")


def render_portfolio_col(portfolio_def, all_data, key_prefix):
    tickers = list(portfolio_def.keys())
    c_sel, c_qty = st.columns([2, 1])
    with c_sel:
        anchor_t = st.selectbox("Anclar por ticker:", ["(ninguno)"] + tickers, key=f"{key_prefix}_t")
    with c_qty:
        anchor_q = None
        if anchor_t != "(ninguno)":
            anchor_q = st.number_input(f"Cant. {anchor_t}:", min_value=1, value=1, step=1, key=f"{key_prefix}_q")
        else:
            st.write("")
    result = calculate_portfolio(
        portfolio_def, all_data,
        anchor_ticker=anchor_t if anchor_t != "(ninguno)" else None,
        anchor_qty=anchor_q
    )
    if result:
        render_portfolio_table(*result)


# ── Título y tabs ─────────────────────────────────────────────────────────────
st.title("Panel de Control Financiero")
tabs = st.tabs(["📊 Análisis Base", "📂 Portfolios", "📋 Opciones", "🔬 Analizador"])


# ─────────────────────────────────────────────
# TAB 1: ANÁLISIS BASE
# ─────────────────────────────────────────────
with tabs[0]:
    c_in, _ = st.columns([1, 5])
    new_t = c_in.text_input("Agregar:", key="add_t", placeholder="Ticker...")
    if new_t:
        new_t = new_t.upper()
        if new_t not in st.session_state.tickers:
            st.session_state.tickers.append(new_t)
            st.rerun()

    cols = st.columns(6)
    for idx, ticker in enumerate(st.session_state.tickers):
        with cols[idx % 6]:
            data = get_ticker_data(ticker)
            if data:
                rsi = data["rsi"]
                alert_cls = "rsi-alert" if rsi >= 70 or rsi <= 30 else "rsi-normal"
                st.markdown(f"""
                <div class="compact-card">
                    <div><span class="t-header">{ticker}</span></div>
                    <div class="t-ratio">Ratio: {CEDEAR_RATIOS.get(ticker, 'N/A')}</div>
                    <div class="p-usd">U$ {data['adr']}</div>
                    <div class="p-ars">A$ {data['local']}</div>
                    <div style="margin-top:4px;"><span class="{alert_cls}">RSI: {rsi}</span></div>
                </div>""", unsafe_allow_html=True)
                if st.button("Quitar", key=f"del_{ticker}", width="stretch"):
                    st.session_state.tickers.remove(ticker)
                    st.rerun()
            else:
                st.error(f"Error {ticker}")
                if st.button("X", key=f"err_{ticker}"):
                    st.session_state.tickers.remove(ticker)
                    st.rerun()


# ─────────────────────────────────────────────
# TAB 2: PORTFOLIOS
# ─────────────────────────────────────────────
with tabs[1]:
    all_data = {t: get_ticker_data(t) for t in set(PORTFOLIO_1) | set(PORTFOLIO_2)}
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.subheader("Portfolio 1")
        render_portfolio_col(PORTFOLIO_1, all_data, "p1")
    with col_p2:
        st.subheader("Portfolio 2")
        render_portfolio_col(PORTFOLIO_2, all_data, "p2")


# ─────────────────────────────────────────────
# TAB 3: OPCIONES
# ─────────────────────────────────────────────
with tabs[2]:
    tickers_tuple = tuple(st.session_state.tickers)

    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        # Selector de UN ticker — la carga es por ticker individual
        ticker_sel = st.selectbox(
            "Ticker:", list(tickers_tuple),
            key="opt_ticker_sel"
        )
    with fc2:
        orden = st.selectbox("Ordenar por:", ["Strike", "Volumen Call", "OI Call", "Volumen Put", "OI Put"], key="opt_orden")
    with fc3:
        rango_opt = st.selectbox("Rango de strikes:", ["Todos", "±5%", "±10%", "±15%", "±20%"], index=2, key="opt_rango")
    with fc4:
        st.write("")
        if st.button("🔄 Recargar", key="opt_reload"):
            get_options_data.clear()
            st.session_state.opt_loaded = False
            st.session_state.opt_ticker_cargado = None

    rango_pct = None if rango_opt == "Todos" else float(rango_opt.replace("±", "").replace("%", ""))

    # Limpiar automáticamente si el ticker cambió desde la última carga
    if st.session_state.get("opt_ticker_cargado") != ticker_sel:
        st.session_state.opt_loaded = False

    # ── Carga bajo demanda ────────────────────
    if not st.session_state.get("opt_loaded", False):
        st.info(f"📋 Presioná **Cargar** para ver las opciones de **{ticker_sel}**.")
        if st.button("⬇ Cargar opciones", key="opt_load", type="primary"):
            st.session_state.opt_loaded = True
            st.session_state.opt_ticker_cargado = ticker_sel
            st.rerun()
    else:
        with st.spinner(f"Cargando opciones de {ticker_sel}..."):
            resultado = get_options_data((ticker_sel,))

        df_long, prices = resultado if isinstance(resultado, tuple) else (resultado, {})

        if df_long.empty:
            st.warning(f"No se encontraron opciones para {ticker_sel} en los próximos 30 días.")
        else:
            precio_actual = prices.get(ticker_sel)
            fechas = sorted(df_long[df_long["ticker"] == ticker_sel]["expira"].unique())
            precio_md = f" — precio actual: **${precio_actual:.2f}**" if precio_actual else ""
            st.markdown(f"### {ticker_sel}{precio_md}")

            for tab_f, fecha in zip(st.tabs([str(f) for f in fechas]), fechas):
                with tab_f:
                    chain = build_unified_chain(df_long, ticker_sel, fecha, precio_actual, rango_pct)
                    dias = int(df_long[(df_long["ticker"] == ticker_sel) & (df_long["expira"] == fecha)]["dias"].iloc[0])
                    st.caption(f"Vence {fecha} — {dias} días")
                    st.html(build_unified_html(chain, precio_actual, orden))


# ─────────────────────────────────────────────
# TAB 4: ANALIZADOR
# ─────────────────────────────────────────────
with tabs[3]:
    # ── Importar CSV ──────────────────────────
    uploaded_csv = st.file_uploader("Importar CSV", type=["csv"], key="val_csv_upload", label_visibility="collapsed")
    if uploaded_csv is not None:
        ticker_csv, data_csv = parse_csv(uploaded_csv.read())
        if data_csv:
            if ticker_csv:
                st.session_state.val_ticker = ticker_csv
                st.session_state.val_ticker_input = ticker_csv
            st.session_state.val_data = data_csv
            for q, d in data_csv.items():
                st.session_state[f"val_price_{q}"]  = d["price"]
                st.session_state[f"val_shares_{q}"] = d["shares"]
                st.session_state[f"val_ocf_{q}"]    = d["ocf"]
                st.session_state[f"val_bb_{q}"]     = d["buyback"]
            st.success(f"CSV importado: {st.session_state.val_ticker}")
        else:
            st.error("No se pudo leer el CSV.")

    col_inputs, col_chart = st.columns([1, 1], gap="large")

    # ── Inputs ────────────────────────────────
    with col_inputs:
        ti1, ti2 = st.columns([2, 1])
        with ti1:
            st.session_state.val_ticker = st.text_input(
                "Ticker", placeholder="Ej: AMAT", key="val_ticker_input"
            ).upper()
        with ti2:
            st.download_button(
                "⬇ Exportar CSV",
                data=export_csv(st.session_state.val_ticker, st.session_state.val_data),
                file_name=f"{st.session_state.val_ticker or 'valuacion'}_valuacion.csv",
                mime="text/csv", key="val_export", width="stretch"
            )

        # Encabezado
        h0, h1, h2, h3, h4, h5 = st.columns([1.1, 1.2, 1.2, 1.2, 1.2, 0.4])
        for col, label in zip([h0, h1, h2, h3, h4, h5],
                               ["Quarter", "Price", "Shares", "Op.CF", "Buyback%", "✕"]):
            colors = {"Price": "#E57373", "Buyback%": "#FFD54F", "✕": "#333"}
            color = colors.get(label, "#555")
            col.markdown(f"<span style='color:{color};font-size:0.75rem'>{label}</span>", unsafe_allow_html=True)

        for q in QUARTERS:
            d = st.session_state.val_data[q]
            c0, c1, c2, c3, c4, c5 = st.columns([1.1, 1.2, 1.2, 1.2, 1.2, 0.4])
            c0.markdown(f"<div style='padding-top:8px;color:#aaa;font-size:0.82rem;font-weight:bold'>{q}</div>", unsafe_allow_html=True)
            d["price"]   = c1.text_input(f"Price {q}",   placeholder="0.00", key=f"val_price_{q}",  label_visibility="collapsed")
            d["shares"]  = c2.text_input(f"Shares {q}",  placeholder="0",    key=f"val_shares_{q}", label_visibility="collapsed")
            d["ocf"]     = c3.text_input(f"OCF {q}",     placeholder="0",    key=f"val_ocf_{q}",    label_visibility="collapsed")
            d["buyback"] = c4.text_input(f"Buyback {q}", placeholder="0.00", key=f"val_bb_{q}",     label_visibility="collapsed")
            if c5.button("✕", key=f"val_clear_{q}", width="stretch"):
                st.session_state.val_data[q] = dict(EMPTY_QUARTER)
                for field in ["price", "shares", "ocf", "buyback"]:
                    st.session_state[f"val_{field}_{q}"] = ""
                st.rerun()

    # ── Gráfico ───────────────────────────────
    with col_chart:
        series = build_series(st.session_state.val_data)
        if not series:
            st.markdown("<div style='color:#444;font-size:0.9rem;margin-top:60px;text-align:center'>Ingresá datos para ver el gráfico</div>", unsafe_allow_html=True)
        else:
            st.plotly_chart(build_chart(series, st.session_state.val_ticker), width="stretch")

    # ── Veredicto ─────────────────────────────
    st.divider()
    st.markdown("#### 📋 Veredicto")
    if len(series) < 2:
        st.info("Ingresá datos de al menos 2 quarters para ver el veredicto.")
    else:
        st.html(render_verdict_html(build_verdict(series), st.session_state.val_ticker))
