"""
valuation.py — lógica pura del Analizador (Tab 4).
Sin dependencias de streamlit: todo lo que hay acá es calculable y testeable
de forma independiente.
"""

import io
import re
import csv
from plotly import graph_objects as go

QUARTERS = ["Q1-26", "Q4-25", "Q3-25", "Q2-25", "Q1-25"]

EMPTY_QUARTER = {"price": "", "shares": "", "ocf": "", "buyback": ""}

# ── Parseo ────────────────────────────────────────────────────────────────────

def parse_float(val) -> float | None:
    """Convierte string a float, acepta coma o punto como decimal."""
    try:
        return float(str(val).replace(",", ".").strip())
    except Exception:
        return None


def ocf_per_share(ocf, shares) -> float | None:
    o, s = parse_float(ocf), parse_float(shares)
    if o is not None and s is not None and s != 0:
        return round(o / s, 4)
    return None


def normalize_label(raw: str) -> str:
    """Normaliza variantes de label de quarter al formato canónico 'Q4-25'."""
    s = raw.strip().upper()
    s = re.sub(r"[\s_/]+", "-", s)        # separadores varios → guión
    s = re.sub(r"(Q\d)(\d{2})$", r"\1-\2", s)  # Q425 → Q4-25
    return s


def normalize_csv_row(row: dict) -> dict:
    """Mapea columnas con distintos nombres al esquema interno."""
    aliases = {
        "shares":  ["shares", "sh", "share"],
        "ocf":     ["ocf", "operating_cash_flow", "op_cash_flow", "opcf"],
        "price":   ["price", "sp", "stock_price", "precio"],
        "buyback": ["buyback", "bb", "buyback_yield", "dillution", "dilution"],
    }
    row_lower = {k.lower().strip(): v for k, v in row.items()}
    result = {}
    for field, candidates in aliases.items():
        for c in candidates:
            if c in row_lower:
                result[field] = str(row_lower[c]).replace(",", ".")
                break
        else:
            result[field] = ""
    return result


def parse_csv(content: bytes) -> tuple[str | None, dict]:
    """
    Parsea CSV en bytes.
    Retorna (ticker, data_dict) donde data_dict es {quarter: {price, shares, ocf, buyback}}.
    """
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return None, {}

    # Detectar ticker
    first = {k.lower().strip(): v for k, v in rows[0].items()}
    ticker = first.get("ticker", "").strip().upper() or None

    data = {q: dict(EMPTY_QUARTER) for q in QUARTERS}
    for row in rows:
        row_lower = {k.lower().strip(): v for k, v in row.items()}
        label = normalize_label(row_lower.get("label", "").strip())
        if label in QUARTERS:
            data[label] = normalize_csv_row(row)

    return ticker, data


def export_csv(ticker: str, data: dict) -> str:
    """Serializa los datos del analizador a CSV."""
    lines = ["ticker,label,price,shares,ocf,buyback"]
    for q in QUARTERS:
        d = data.get(q, EMPTY_QUARTER)
        lines.append(f"{ticker or 'TICKER'},{q},{d['price']},{d['shares']},{d['ocf']},{d['buyback']}")
    return "\n".join(lines)


# ── Series para gráfico y veredicto (loop único) ──────────────────────────────

def build_series(data: dict) -> list[dict]:
    """
    Itera los quarters en orden cronológico y construye una lista de dicts con
    todas las métricas derivadas. Usado tanto por el gráfico como por el veredicto.
    Excluye quarters sin datos.
    """
    series = []
    for q in reversed(QUARTERS):  # cronológico: Q1-25 → Q1-26
        d = data.get(q, EMPTY_QUARTER)
        p   = parse_float(d["price"])
        ops = ocf_per_share(d["ocf"], d["shares"])
        bb  = parse_float(d["buyback"])
        sh  = parse_float(d["shares"])
        ocf = parse_float(d["ocf"])

        if p is None and ops is None:
            continue

        pocf = round(p / ops, 2) if (p and ops and ops != 0) else None
        series.append({
            "q":     q,
            "price": p,
            "ocfps": ops,
            "bb":    bb,
            "shares": sh,
            "ocf":   ocf,
            "pocf":  pocf,
        })
    return series


# ── Gráfico ───────────────────────────────────────────────────────────────────

def build_chart(series: list[dict], ticker_label: str) -> go.Figure:
    """Construye la figura Plotly a partir de las series."""
    labels    = [r["q"]     for r in series]
    prices_v  = [r["price"] for r in series]
    ocfps     = [r["ocfps"] for r in series]
    buybacks  = [r["bb"]    for r in series]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=labels, y=ocfps, name="OCF/Share",
        mode="lines+markers",
        line=dict(color="#1565C0", width=2.5),
        marker=dict(size=7, color="#1E88E5"),
        yaxis="y1", connectgaps=False,
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=buybacks, name="Buyback %",
        mode="lines+markers",
        line=dict(color="#F9A825", width=2, dash="dot"),
        marker=dict(size=6, color="#F9A825"),
        yaxis="y2", connectgaps=False,
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=prices_v, name="Stock Price",
        mode="lines+markers",
        line=dict(color="#E53935", width=2.5),
        marker=dict(size=7, color="#E53935"),
        yaxis="y3", connectgaps=False,
    ))

    fig.update_layout(
        title=dict(text=ticker_label, font=dict(color="#ccc", size=14), x=0.5),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        height=320,
        margin=dict(l=60, r=110, t=40, b=40),
        legend=dict(
            orientation="h", x=0.5, xanchor="center", y=1.12,
            font=dict(color="#aaa", size=11), bgcolor="rgba(0,0,0,0)"
        ),
        xaxis=dict(
            tickfont=dict(color="#888", size=11),
            gridcolor="#1e1e1e", linecolor="#333",
            domain=[0, 0.84],
        ),
        yaxis=dict(
            title=dict(text="OCF/Share", font=dict(color="#1E88E5", size=10)),
            tickfont=dict(color="#1E88E5", size=10),
            gridcolor="#1a1a2e", side="left",
        ),
        yaxis2=dict(
            # Buyback % — primer eje derecho, pegado al plot
            title=dict(text="Buyback %", font=dict(color="#F9A825", size=10)),
            tickfont=dict(color="#F9A825", size=10),
            overlaying="y", side="right",
            anchor="x",
            gridcolor="rgba(0,0,0,0)", showgrid=False, tickformat=".2f",
        ),
        yaxis3=dict(
            # Stock Price — segundo eje derecho, más afuera
            title=dict(text="Price", font=dict(color="#E53935", size=10)),
            tickfont=dict(color="#E53935", size=10),
            overlaying="y", side="right",
            anchor="free", position=0.95,
            gridcolor="rgba(0,0,0,0)", showgrid=False,
        ),
        hovermode="x unified",
    )
    return fig


# ── Veredicto ─────────────────────────────────────────────────────────────────

def pct_change(a, b) -> float | None:
    if a and b and a != 0:
        return round((b - a) / abs(a) * 100, 1)
    return None


def fmt_pct(v, pos_prefix="+") -> str:
    if v is None:
        return "—"
    prefix = pos_prefix if v >= 0 else ""
    return f"{prefix}{v:.1f}%"


def badge_color(v, good_positive=True) -> str:
    if v is None:
        return "#888"
    if good_positive:
        return "#4CAF50" if v > 0 else ("#EF5350" if v < 0 else "#888")
    return "#EF5350" if v > 0 else ("#4CAF50" if v < 0 else "#888")


def build_verdict(series: list[dict]) -> dict:
    """
    Calcula todas las métricas del veredicto a partir de las series.
    Retorna un dict con todo lo necesario para renderizar el HTML.
    """
    first, last = series[0], series[-1]

    price_chg  = pct_change(first["price"],  last["price"])
    ocfps_chg  = pct_change(first["ocfps"],  last["ocfps"])
    pocf_chg   = pct_change(first["pocf"],   last["pocf"])
    shares_chg = pct_change(first["shares"], last["shares"])

    bb_vals  = [r["bb"] for r in series if r["bb"] is not None]
    bb_total = round(sum(bb_vals), 2) if bb_vals else None
    hubo_dil = any(r["bb"] is not None and r["bb"] < 0 for r in series)
    hubo_bb  = any(r["bb"] is not None and r["bb"] > 0 for r in series)

    # Tendencia OCF quarter a quarter
    ocf_deltas = [
        series[i]["ocfps"] - series[i-1]["ocfps"]
        for i in range(1, len(series))
        if series[i]["ocfps"] and series[i-1]["ocfps"]
    ]
    if ocf_deltas:
        rising  = sum(1 for d in ocf_deltas if d > 0)
        falling = sum(1 for d in ocf_deltas if d < 0)
        if rising > falling:
            ocf_trend_label, ocf_trend_color = "📈 acelerando", "#4CAF50"
        elif falling > rising:
            ocf_trend_label, ocf_trend_color = "📉 desacelerando", "#EF5350"
        else:
            ocf_trend_label, ocf_trend_color = "➡ lateral", "#888"
    else:
        ocf_trend_label, ocf_trend_color = "—", "#888"

    # Momentum
    if price_chg is not None and ocfps_chg is not None:
        gap = round(price_chg - ocfps_chg, 1)
        if ocfps_chg > 0 and price_chg < 0:
            momentum_label, momentum_color = "🟢 OCF sube, precio baja — posible oportunidad", "#4CAF50"
        elif ocfps_chg > 0 and price_chg > 0 and gap > 15:
            momentum_label = f"🟡 Precio superó al OCF/share por {gap:.1f}pp — múltiplo expandido"
            momentum_color = "#FFA726"
        elif ocfps_chg < 0 and price_chg > 0:
            momentum_label, momentum_color = "🔴 Precio sube pero OCF/share cae — deterioro operativo", "#EF5350"
        elif ocfps_chg > 0 and price_chg > 0 and gap <= 15:
            momentum_label, momentum_color = "🟢 Precio y OCF/share alineados — crecimiento sano", "#4CAF50"
        else:
            momentum_label, momentum_color = "⚪ Sin señal clara de momentum", "#888"
    else:
        gap = None
        momentum_label, momentum_color = "—", "#888"

    # Eficiencia buyback
    if shares_chg is not None and bb_total is not None:
        if shares_chg < -0.5:
            bb_eff_label = f"✅ Shares bajaron {fmt_pct(shares_chg)} — buyback efectivo"
            bb_eff_color = "#4CAF50"
        elif shares_chg > 0.5 and bb_total > 0:
            bb_eff_label = f"⚠️ Shares subieron {fmt_pct(shares_chg)} pese a buyback — dilución por stock comp"
            bb_eff_color = "#FFA726"
        elif shares_chg > 0.5:
            bb_eff_label = f"🔴 Shares subieron {fmt_pct(shares_chg)} — dilución neta"
            bb_eff_color = "#EF5350"
        else:
            bb_eff_label = f"➡ Shares estables ({fmt_pct(shares_chg)})"
            bb_eff_color = "#888"
    else:
        bb_eff_label, bb_eff_color = "—", "#888"

    # Narrativa
    if price_chg is not None and ocfps_chg is not None and bb_total is not None:
        if price_chg > 0 and ocfps_chg > 0:
            narrativa = f"El precio subió <b>{fmt_pct(price_chg)}</b> y el OCF/share <b>{fmt_pct(ocfps_chg)}</b> en el período."
        elif price_chg > 0 and ocfps_chg <= 0:
            narrativa = f"El precio subió <b>{fmt_pct(price_chg)}</b> pero el OCF/share cayó <b>{fmt_pct(ocfps_chg)}</b> — la suba es solo de múltiplo."
        elif price_chg <= 0 and ocfps_chg > 0:
            narrativa = f"El precio cayó <b>{fmt_pct(price_chg)}</b> mientras el OCF/share creció <b>{fmt_pct(ocfps_chg)}</b> — posible compresión injustificada."
        else:
            narrativa = f"Tanto el precio (<b>{fmt_pct(price_chg)}</b>) como el OCF/share (<b>{fmt_pct(ocfps_chg)}</b>) cayeron en el período."

        if hubo_dil and not hubo_bb:
            narrativa += f" Hubo dilución neta (buyback acumulado: <b>{fmt_pct(bb_total)}</b>)."
        elif hubo_bb and not hubo_dil:
            narrativa += f" Se recompraron acciones (<b>{fmt_pct(bb_total)}</b> acumulado)."
        elif hubo_bb and hubo_dil:
            narrativa += f" Hubo quarters con recompra y otros con dilución (neto: <b>{fmt_pct(bb_total)}</b>)."
    else:
        narrativa = "Datos insuficientes para narrativa completa."

    return {
        "first": first, "last": last,
        "price_chg": price_chg, "ocfps_chg": ocfps_chg,
        "pocf_chg": pocf_chg, "shares_chg": shares_chg,
        "bb_total": bb_total, "hubo_dil": hubo_dil, "hubo_bb": hubo_bb,
        "ocf_trend_label": ocf_trend_label, "ocf_trend_color": ocf_trend_color,
        "momentum_label": momentum_label, "momentum_color": momentum_color,
        "bb_eff_label": bb_eff_label, "bb_eff_color": bb_eff_color,
        "narrativa": narrativa,
        "n_q": len(series),
        "span": f"{series[0]['q']} → {series[-1]['q']}",
    }


def render_verdict_html(v: dict, ticker: str) -> str:
    """Genera el HTML del bloque de veredicto a partir del dict de build_verdict."""
    f, l = v["first"], v["last"]

    def card(label, value_html, subtitle):
        return f"""
        <div style="background:#1a1a1a;border-radius:4px;padding:8px 14px;min-width:110px;">
          <div style="color:#555;font-size:0.72rem;margin-bottom:2px">{label}</div>
          {value_html}
          <div style="color:#444;font-size:0.7rem">{subtitle}</div>
        </div>"""

    def metric(val, good_positive=True):
        return f'<div style="color:{badge_color(val, good_positive)};font-size:1.1rem;font-weight:bold">{fmt_pct(val)}</div>'

    bb_label = (
        "Con dilución" if v["hubo_dil"] and not v["hubo_bb"] else
        "Solo buyback" if v["hubo_bb"] and not v["hubo_dil"] else
        "Mixto"        if v["hubo_bb"] and v["hubo_dil"] else "—"
    )

    ocfps_f = f"{f['ocfps']:.2f}" if f["ocfps"] else "—"
    ocfps_l = f"{l['ocfps']:.2f}" if l["ocfps"] else "—"

    cards = (
        card("Precio",       metric(v["price_chg"]),
             f"${f['price'] or '—'} → ${l['price'] or '—'}") +
        card("OCF/Share",    metric(v["ocfps_chg"]),
             f"{ocfps_f} → {ocfps_l}") +
        card("P/OCF múltiplo", metric(v["pocf_chg"], good_positive=False),
             f"{f['pocf'] or '—'}x → {l['pocf'] or '—'}x") +
        card("Buyback acum.", metric(v["bb_total"]) if v["bb_total"] is not None
             else '<div style="color:#888;font-size:1.1rem;font-weight:bold">—</div>', bb_label) +
        card("Tendencia OCF",
             f'<div style="color:{v["ocf_trend_color"]};font-size:0.9rem;font-weight:bold;margin-top:4px">{v["ocf_trend_label"]}</div>',
             "")
    )

    def signal(label, color, text):
        return f"""
        <div style="color:{color};background:#1a1a1a;border-left:3px solid {color};
                    padding:5px 10px;border-radius:0 4px 4px 0;">
          <b>{label}</b> {text}
        </div>"""

    return f"""
    <div style="font-family:Arial,sans-serif;font-size:0.83rem;background:#111;
                border:1px solid #2a2a2a;border-radius:6px;padding:16px 20px;margin-top:8px;">
      <div style="color:#aaa;margin-bottom:12px;">
        <b style="color:white;font-size:1rem">{ticker or 'Ticker'}</b>
        &nbsp;<span style="color:#555">{v['span']} ({v['n_q']} quarters)</span>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px;">{cards}</div>
      <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:14px;">
        {signal("Momentum:", v["momentum_color"], v["momentum_label"])}
        {signal("Shares:", v["bb_eff_color"], v["bb_eff_label"])}
      </div>
      <div style="color:#bbb;background:#161616;border-radius:4px;padding:8px 12px;
                  border:1px solid #222;line-height:1.6;">
        {v["narrativa"]}
      </div>
    </div>
    """