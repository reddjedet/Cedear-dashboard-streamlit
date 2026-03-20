import math

# Definición de los portfolios: ticker -> peso objetivo (%)
PORTFOLIO_1 = {
    "DE":   11.78,
    "MRK":   6.15,
    "LLY":  18.54,
    "NEM":  43.31,
    "MSTR":  0.80,
    "COST":  7.79,
    "PEP":   5.89,
    "PAM":   5.74,
}

PORTFOLIO_2 = {
    "CAT":  22.42,
    "MRK":  38.07,
    "GOOGL":16.87,
    "MA":    2.31,
    "PM":    8.49,
    "AMAT":  9.83,
    # nota: suma = 97.99%, se normalizará internamente
}


def get_price_for_portfolio(ticker, data):
    """
    Devuelve el precio en ARS que se usa para calcular el portfolio.
    PAM -> precio local (acción, no ADR)
    Resto -> precio .BA (CEDEAR local)
    Retorna None si no hay dato disponible.
    """
    if data is None:
        return None
    price = data.get("local", 0.0)
    return price if price and price > 0 else None


def calculate_portfolio(portfolio_weights, all_data, anchor_ticker=None, anchor_qty=None):
    """
    Calcula cantidades nominales para respetar los pesos del portfolio.

    Parámetros:
    - portfolio_weights: dict {ticker: peso_%}
    - all_data: dict {ticker: data_dict} con precios y RSI
    - anchor_ticker: ticker ancla (el que el usuario fijó)
    - anchor_qty: cantidad nominal del ancla

    Retorna lista de dicts con info por ticker.
    """
    # Normalizar pesos a 100%
    total_w = sum(portfolio_weights.values())
    weights = {t: w / total_w * 100 for t, w in portfolio_weights.items()}

    # Obtener precios
    prices = {}
    for ticker in weights:
        data = all_data.get(ticker)
        price = get_price_for_portfolio(ticker, data)
        if price:
            prices[ticker] = price

    # Si no hay ancla, calcular en base a 1 unidad del ticker más barato
    # para obtener un portfolio "mínimo representativo"
    if anchor_ticker and anchor_ticker in prices and anchor_qty and anchor_qty > 0:
        # Valor total del portfolio basado en la ancla
        anchor_weight = weights[anchor_ticker] / 100
        anchor_value = prices[anchor_ticker] * anchor_qty
        total_portfolio_value = anchor_value / anchor_weight
    else:
        # Sin ancla: usamos el primer ticker disponible con qty=1 para escalar
        # Buscamos el ticker que con qty=1 da el portfolio más "entero"
        if not prices:
            return []
        # Tomamos el ticker con mayor peso como referencia con qty=1
        ref_ticker = max((t for t in weights if t in prices), key=lambda t: weights[t])
        ref_value = prices[ref_ticker] * 1
        ref_weight = weights[ref_ticker] / 100
        total_portfolio_value = ref_value / ref_weight

    # Calcular cantidades ideales y redondear
    results = []
    total_real_ars = 0.0

    for ticker, weight in weights.items():
        price = prices.get(ticker)
        rsi = all_data.get(ticker, {}).get("rsi") if all_data.get(ticker) else None

        if price is None or price <= 0:
            results.append({
                "ticker": ticker,
                "weight_target": round(weight, 2),
                "qty_ideal": None,
                "qty_rounded": None,
                "cost_ars": None,
                "weight_real": None,
                "error_pct": None,
                "price": None,
                "rsi": rsi,
            })
            continue

        qty_ideal = (weight / 100) * total_portfolio_value / price
        qty_rounded = max(1, round(qty_ideal))
        cost_ars = qty_rounded * price
        total_real_ars += cost_ars

        results.append({
            "ticker": ticker,
            "weight_target": round(weight, 2),
            "qty_ideal": qty_ideal,
            "qty_rounded": qty_rounded,
            "cost_ars": cost_ars,
            "price": price,
            "rsi": rsi,
        })

    # Calcular peso real y error después de tener el total
    for r in results:
        if r["cost_ars"] is not None and total_real_ars > 0:
            r["weight_real"] = round(r["cost_ars"] / total_real_ars * 100, 2)
            r["error_pct"] = round(r["weight_real"] - r["weight_target"], 2)
        else:
            r["weight_real"] = None
            r["error_pct"] = None

    return results, total_real_ars