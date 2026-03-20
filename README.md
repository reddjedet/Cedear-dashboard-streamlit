# Panel de Control Financiero

Dashboard financiero construido con Streamlit para seguimiento de CEDEARs y acciones que cotizan en bolsa.

## Secciones

### 📊 Análisis Base
Tarjetas en tiempo real con precio ADR (USD), precio local (ARS) y RSI para cada ticker. Permite agregar y quitar tickers dinámicamente.

### 📂 Portfolios
Dos portfolios precargados con pesos objetivo (%). Ingresás la cantidad de un ticker ancla y el sistema calcula automáticamente cuántas unidades necesitás de cada instrumento para respetar los pesos, mostrando el margen de error por redondeo.

### 📋 Opciones
Cadena de opciones (calls y puts) para los próximos 30 días, en formato unificado `Call | Strike | Put` con highlight del precio actual y filtro de rango de strikes. Carga bajo demanda para no afectar la performance general.

### 🔬 Analizador
Herramienta de valuación por quarters. Permite ingresar manualmente o importar vía CSV hasta 5 quarters de datos financieros (precio, shares, OCF, buyback yield) y genera:
- Gráfico comparativo con triple eje (OCF/Share, Stock Price, Buyback %)
- Veredicto automático con métricas de momentum, tendencia OCF, eficiencia de buyback y narrativa comparativa

## Instalación

```bash
git clone <repo>
cd <repo>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run main.py
```

## Estructura

```
├── main.py          # UI principal — tabs y widgets
├── logic.py         # Descarga de precios y RSI vía yfinance
├── portfolio.py     # Cálculo de cantidades nominales por portfolio
├── options.py       # Descarga y renderizado de cadena de opciones
├── valuation.py     # Lógica del analizador: parseo CSV, gráfico, veredicto
├── requirements.txt
└── examples/
    ├── amat_valuacion.csv
    └── lly_valuacion.csv
```

## Formato CSV para importar

El analizador acepta CSV con las siguientes columnas (los nombres de columna son flexibles):

| Campo | Nombres aceptados |
|---|---|
| Ticker | `ticker` |
| Quarter | `label` — formatos: `Q4-25`, `Q4 25`, `Q425`, `q4/25` |
| Precio | `price`, `sp`, `stock_price`, `precio` |
| Shares | `shares`, `sh`, `share` |
| OCF | `ocf`, `operating_cash_flow`, `op_cash_flow` |
| Buyback % | `buyback`, `bb`, `buyback_yield`, `dilution` |

Ejemplo mínimo:
```csv
ticker,label,price,shares,ocf,buyback
AMAT,Q1-26,324.74,793,1686,1.59
AMAT,Q4-25,256.99,794,2828,2.69
```

## Notas
- Los precios de CEDEARs se toman del mercado local (`.BA`) vía yfinance
- PAM usa precio de la acción local (`PAMP.BA`), no del ADR
- El RSI se calcula con el método de Wilder (EWM) sobre datos intradía con fallback a diario
- Las opciones corresponden a los tickers del ADR (mercado americano)
