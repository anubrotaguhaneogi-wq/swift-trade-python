
"""
Swift Trade | Swing Scanner (Offline CSV Edition)
Purpose: 15-30 trading-day swing setups using historical OHLCV data.
No live feed, broker API, or internet download is used.

CSV format:
symbol,date,open,high,low,close,volume

Required packages:
streamlit
pandas
numpy
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

# -------------------- SETTINGS --------------------
APP_TITLE = "Swift Trade | Swing Scanner"
TOP_N = 6
HOLD_MIN_DAYS = 15
HOLD_MAX_DAYS = 30
RSI_MIN = 50.0
RSI_MAX = 68.0
MIN_VOLUME_RATIO = 1.20
BREAKOUT_LOOKBACK = 20
ATR_PERIOD = 14
TICK_SIZE = 0.05

REQUIRED_COLUMNS = [
    "symbol", "date", "open", "high", "low", "close", "volume"
]

# -------------------- PAGE --------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(145deg,#081321,#10243a);
    color: #e8eef7;
}
.block-container {
    max-width: 1400px;
    padding-top: 1.2rem;
}
h1,h2,h3 {
    color: #f4c95d;
}
[data-testid="stMetric"] {
    background: #102b43;
    padding: 12px;
    border: 1px solid #28445d;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# -------------------- INDICATORS --------------------
def calculate_rsi(
    series: pd.Series,
    period: int = 14
) -> pd.Series:
    delta = series.diff()

    gain = delta.clip(lower=0).ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    loss = (-delta.clip(upper=0)).ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50.0)


def calculate_atr(
    df: pd.DataFrame,
    period: int = ATR_PERIOD
) -> pd.Series:

    prev_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()


# -------------------- CSV DATA VALIDATION --------------------
def normalize_upload(
    raw: pd.DataFrame
) -> Tuple[pd.DataFrame, List[str]]:

    df = raw.copy()

    df.columns = [
        str(c).strip().lower()
        for c in df.columns
    ]

    missing = [
        c for c in REQUIRED_COLUMNS
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing CSV columns: " + ", ".join(missing)
        )

    df = df[REQUIRED_COLUMNS].copy()

    df["symbol"] = (
        df["symbol"].astype(str).str.strip().str.upper()
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(subset=REQUIRED_COLUMNS)

    price_valid = (
        (df[["open", "high", "low", "close"]] > 0)
        .all(axis=1)
    )

    df = df[
        (df["symbol"] != "")
        & price_valid
        & (df["volume"] >= 0)
    ]

    df = df[
        (df["high"] >= df[["open", "close", "low"]].max(axis=1))
        & (df["low"] <= df[["open", "close", "high"]].min(axis=1))
    ]

    df = df.drop_duplicates(
        ["symbol", "date"],
        keep="last"
    )

    df = df.sort_values(
        ["symbol", "date"]
    ).reset_index(drop=True)

    if df.empty:
        raise ValueError(
            "No valid OHLCV rows found in the uploaded CSV."
        )

    warnings = []

    counts = df.groupby("symbol")["date"].nunique()
    short = counts[counts < 60]
    today = pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None)
    latest_dates = df.groupby("symbol")["date"].max()
    stale_symbols = latest_dates[latest_dates < today - pd.Timedelta(days=7)]

    if not stale_symbols.empty:
        raise ValueError(
            "Stale market data detected for: "
            + ", ".join(stale_symbols.index.astype(str))
    )
    
    if not short.empty:
        warnings.append(
            "Some symbols have fewer than 60 daily candles. "
            "Longer-term trend checks may be unavailable."
        )

    return df, warnings


# -------------------- SYMBOL ANALYSIS --------------------
def analyze_symbol(df: pd.DataFrame) -> dict:

    d = (
        df.sort_values("date")
        .drop_duplicates("date")
        .copy()
    )

    if len(d) < 60:
        return {
            "symbol": str(d["symbol"].iloc[-1]),
            "status": "INSUFFICIENT DATA",
            "score": 0,
            "reason": (
                f"Only {len(d)} daily candles; "
                "need at least 60."
            )
        }

    close = d["close"]

    d["ema20"] = close.ewm(
        span=20, adjust=False
    ).mean()

    d["ema50"] = close.ewm(
        span=50, adjust=False
    ).mean()

    d["ema200"] = close.ewm(
        span=200, adjust=False
    ).mean()

    d["rsi14"] = calculate_rsi(close, 14)
    d["atr14"] = calculate_atr(d, ATR_PERIOD)

    d["avg_vol20"] = (
        d["volume"].shift(1)
        .rolling(20, min_periods=15)
        .mean()
    )

    d["prior_high20"] = (
        d["high"].shift(1)
        .rolling(BREAKOUT_LOOKBACK, min_periods=15)
        .max()
    )

    last = d.iloc[-1]
    prev = d.iloc[-2]

    price = float(last["close"])

    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    ema200 = float(last["ema200"])

    rsi = float(last["rsi14"])

    atr = (
        float(last["atr14"])
        if pd.notna(last["atr14"])
        else np.nan
    )

    avg_vol = (
        float(last["avg_vol20"])
        if pd.notna(last["avg_vol20"])
        else np.nan
    )

    vol_ratio = (
        float(last["volume"] / avg_vol)
        if pd.notna(avg_vol) and avg_vol > 0
        else np.nan
    )

    resistance = (
        float(last["prior_high20"])
        if pd.notna(last["prior_high20"])
        else np.nan
    )

    # Weekly trend confirmation
    weekly = (
        d.set_index("date")
        .resample("W-FRI")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum")
        )
        .dropna(subset=["close"])
    )

    weekly_up = False

    if len(weekly) >= 12:
        w20 = weekly["close"].ewm(
            span=10, adjust=False
        ).mean().iloc[-1]

        w40 = weekly["close"].ewm(
            span=20, adjust=False
        ).mean().iloc[-1]

        weekly_up = bool(
            weekly["close"].iloc[-1] > w20 > w40
        )


    # Daily trend and momentum filters
    trend = price > ema20 > ema50
    long_trend = price > ema200
    momentum = RSI_MIN <= rsi <= RSI_MAX

    volume_ok = bool(
        np.isfinite(vol_ratio)
        and vol_ratio >= MIN_VOLUME_RATIO
    )

    breakout = bool(
        np.isfinite(resistance)
        and price > resistance
    )

    pullback_reclaim = bool(
        price > ema20
        and float(prev["close"]) <= float(prev["ema20"])
    )

    not_extended = (
        bool(price <= ema20 + (2.5 * atr))
        if np.isfinite(atr)
        else False
    )

    checks = [
        trend,
        long_trend,
        weekly_up,
        momentum,
        volume_ok,
        (breakout or pullback_reclaim),
        not_extended
    ]

    score = int(
        round(100 * sum(checks) / len(checks))
    )

    # Risk and reward levels
    risk_per_share = (
    max(1.5 * atr, price * 0.06)
    if np.isfinite(atr)
    else price * 0.08
)

stop = max(TICK_SIZE, price - risk_per_share)
target1 = price + (2.0 * risk_per_share)
target2 = price + (3.0 * risk_per_share)

    entry_low = (
        price - (0.25 * atr)
        if np.isfinite(atr)
        else price * 0.99
    )

    entry_high = (
        price + (0.25 * atr)
        if np.isfinite(atr)
        else price * 1.01
    )
            entry_price = (entry_low + entry_high) / 2

            risk_per_share = (
                    max(1.5 * atr, entry_price * 0.04)
                    if np.isfinite(atr) and atr > 0
                    else entry_price * 0.06
        )

            risk_per_share = min(risk_per_share, entry_price * 0.10)

            stop = max(TICK_SIZE, entry_price - risk_per_share)
            target1 = entry_price + (2.0 * risk_per_share)
            target2 = entry_price + (3.0 * risk_per_share)
    if (
        score >= 85
        and trend
        and long_trend
        and momentum
        and volume_ok
        and (breakout or pullback_reclaim)
        and not_extended
    ):
        status = "SWING CANDIDATE"

    elif score >= 70:
        status = "WATCHLIST"

    else:
        status = "REJECT"

    reasons = []

    for label, ok in [
        ("Daily uptrend", trend),
        ("Above EMA200", long_trend),
        ("Weekly uptrend", weekly_up),
        ("RSI in range", momentum),
        ("Volume confirmation", volume_ok),
        ("Breakout/pullback", breakout or pullback_reclaim),
        ("Not overextended", not_extended)
    ]:
        if not ok:
            reasons.append(label + " failed")

    return {
        "symbol": str(last["symbol"]),
        "date": pd.Timestamp(last["date"]).date().isoformat(),
        "close": round(price, 2),
        "status": status,
        "score": score,
        "rsi14": round(rsi, 1),

        "volume_ratio": (
            round(vol_ratio, 2)
            if np.isfinite(vol_ratio)
            else np.nan
        ),

        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "weekly_uptrend": weekly_up,
        "breakout20": breakout,

        "entry_low": (
            round(max(TICK_SIZE, entry_low) / TICK_SIZE)
            * TICK_SIZE
        ),

        "entry_high": (
            round(max(TICK_SIZE, entry_high) / TICK_SIZE)
            * TICK_SIZE
        ),

        "stop_loss": (
            round(stop / TICK_SIZE) * TICK_SIZE
        ),

        "target_1": (
            round(target1 / TICK_SIZE) * TICK_SIZE
        ),

        "target_2": (
            round(target2 / TICK_SIZE) * TICK_SIZE
        ),

        "holding_window": (
            f"{HOLD_MIN_DAYS}-{HOLD_MAX_DAYS} trading days"
        ),

        "failed_checks": (
            ", ".join(reasons)
            if reasons
            else "All core checks passed"
        )
    }


# -------------------- SCAN ALL SYMBOLS --------------------
def scan_universe(df: pd.DataFrame) -> pd.DataFrame:

    rows = []

    for symbol, group in df.groupby("symbol"):
        rows.append(analyze_symbol(group))

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    order = {
        "SWING CANDIDATE": 0,
        "WATCHLIST": 1,
        "REJECT": 2,
        "INSUFFICIENT DATA": 3
    }

    result["_order"] = (
        result["status"].map(order).fillna(9)
    )

    result = (
        result.sort_values(
            ["_order", "score"],
            ascending=[True, False]
        )
        .drop(columns="_order")
    )

    return result.reset_index(drop=True)


# -------------------- USER INTERFACE --------------------
st.markdown("# 📈 SWIFT TRADE — SWING SCANNER")

st.caption(
    "Offline edition • Daily + Weekly trend • "
    "Intended holding window: 15–30 trading days"
)

st.warning(
    "This version does not fetch live or historical prices "
    "from the internet. Upload genuine historical OHLCV CSV data. "
    "Demo/synthetic data must never be used for real trading decisions."
)

with st.expander("CSV format required", expanded=True):

    st.code(
        "symbol,date,open,high,low,close,volume\n"
        "RELIANCE,2026-01-01,1200,1220,1190,1210,1500000"
    )

    st.write(
        "Upload one CSV containing one row per symbol per trading day. "
        "For reliable analysis, aim for at least 200 daily candles per symbol."
    )


uploaded = st.file_uploader(
    "Upload historical daily OHLCV CSV",
    type=["csv"]
)

if uploaded is None:

    st.info(
        "No market data loaded. Upload a genuine historical CSV "
        "to run the scanner. No artificial BUY signals are generated."
    )

    st.stop()


try:

    raw = pd.read_csv(uploaded)

    market_data, data_warnings = normalize_upload(raw)

except Exception as exc:

    st.error(f"CSV validation failed: {exc}")
    st.stop()


for warning in data_warnings:
    st.warning(warning)


results = scan_universe(market_data)


# -------------------- SUMMARY METRICS --------------------
c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Symbols loaded",
    int(market_data["symbol"].nunique())
)

c2.metric(
    "Daily rows",
    int(len(market_data))
)

c3.metric(
    "Swing candidates",
    int((results["status"] == "SWING CANDIDATE").sum())
)

c4.metric(
    "Watchlist",
    int((results["status"] == "WATCHLIST").sum())
)


# -------------------- TOP SIX --------------------
st.subheader("Top Swing Candidates (maximum 6)")

candidates = (
    results[
        results["status"].isin([
            "SWING CANDIDATE",
            "WATCHLIST"
        ])
    ]
    .head(TOP_N)
)

if candidates.empty:

    st.info(
        "No symbols passed the current filters. "
        "Do not loosen filters just to force BUY signals."
    )

else:

    display_cols = [
        "symbol",
        "status",
        "score",
        "close",
        "rsi14",
        "volume_ratio",
        "entry_low",
        "entry_high",
        "stop_loss",
        "target_1",
        "target_2",
        "holding_window"
    ]

    st.dataframe(
        candidates[display_cols],
        use_container_width=True,
        hide_index=True
    )


# -------------------- FULL RESULTS --------------------
st.subheader("Full Scan Results")

st.dataframe(
    results,
    use_container_width=True,
    hide_index=True
)


# -------------------- REJECTION REASONS --------------------
st.subheader("Why a symbol did not qualify")

selected = st.selectbox(
    "Select symbol",
    results["symbol"].tolist()
)

selected_row = results[
    results["symbol"] == selected
].iloc[0]

st.write(
    selected_row.get(
        "failed_checks",
        selected_row.get(
            "reason",
            "No additional details."
        )
    )
)


# -------------------- DOWNLOAD RESULTS --------------------
st.download_button(
    "Download scan results CSV",
    data=results.to_csv(index=False).encode("utf-8"),
    file_name="swift_trade_swing_scan_results.csv",
    mime="text/csv"
)


# -------------------- FINAL NOTICE --------------------
st.caption(
    "Research/testing tool only. Levels are rule-based estimates, "
    "not guaranteed outcomes. Review liquidity, corporate actions, "
    "earnings/events, slippage, and position sizing before any trade."
  )
  
