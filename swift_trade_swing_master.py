"""
Swift Trade | Professional Swing Scanner (Offline CSV Edition)
Purpose: 15-30 trading-day swing setups using historical OHLCV data.
No live feed, no broker API, no internet price fetching.

CSV columns: symbol,date,open,high,low,close,volume
Use genuine daily market data. Signals are research outputs, not trade instructions.
"""

from __future__ import annotations

from typing import List, Tuple, Dict, Any
import numpy as np
import pandas as pd
import streamlit as st

# ============================================================
# SETTINGS
# ============================================================
APP_TITLE = "Swift Trade | Professional Swing Scanner"
TOP_N = 6
HOLD_MIN_DAYS = 15
HOLD_MAX_DAYS = 30
RSI_PERIOD = 14
RSI_MIN = 50.0
RSI_MAX = 68.0
MIN_VOLUME_RATIO = 1.20
BREAKOUT_LOOKBACK = 20
ATR_PERIOD = 14
TICK_SIZE = 0.05
MIN_CANDLES = 250
MIN_COMPLETED_WEEKS = 40
STALE_DAYS = 10

REQUIRED_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]

# ============================================================
# PAGE CONFIG & STYLE
# ============================================================
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(145deg, #0b1320, #132337); color: #e8eef7; }
    .block-container { max-width: 1450px; padding-top: 1.4rem; }
    h1, h2, h3 { color: #f4c95d !important; }
    [data-testid="stMetric"] { background: #162d45; padding: 14px 16px; border: 1px solid #2a4a6a; border-radius: 12px; }
    div[data-testid="stDataFrame"] { border: 1px solid #2a4a6a; border-radius: 10px; }
    .stDownloadButton button { background-color: #1e4d7b !important; color: white !important; border-radius: 8px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# INDICATORS
# ============================================================
def calculate_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder-style RSI with explicit handling of zero-gain/zero-loss windows."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
    return rsi


def calculate_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def round_to_tick(value: float, tick: float = TICK_SIZE) -> float:
    if not np.isfinite(value) or tick <= 0:
        return np.nan
    return round(round(value / tick) * tick, 2)

# ============================================================
# DATA VALIDATION & CLEANING
# ============================================================
def normalize_upload(raw: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    if raw is None or raw.empty:
        raise ValueError("The uploaded CSV is empty.")

    df = raw.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    if pd.Index(df.columns).duplicated().any():
        duplicates = pd.Index(df.columns)[pd.Index(df.columns).duplicated()].unique().tolist()
        raise ValueError(f"Duplicate column names after normalization: {', '.join(duplicates)}")

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    df = df[REQUIRED_COLUMNS].copy()

    # Remove missing symbols BEFORE converting to string; otherwise NaN becomes 'NAN'.
    df["symbol"] = df["symbol"].replace(r"^\s*$", np.nan, regex=True)
    df = df.dropna(subset=["symbol"])
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()

    # Parse timestamps consistently, then use India-local calendar dates without timezone.
    parsed_dates = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df["date"] = parsed_dates.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None).dt.normalize()

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Reject NaN and +/- infinity in every required field.
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=REQUIRED_COLUMNS)

    # Basic price and volume constraints.
    price_valid = (df[["open", "high", "low", "close"]] > 0).all(axis=1)
    volume_valid = df["volume"] >= 0
    df = df[(df["symbol"] != "") & price_valid & volume_valid]

    # OHLC consistency: high must cover open/close/low; low must not exceed open/close.
    valid_high = df["high"] >= df[["open", "close", "low"]].max(axis=1)
    valid_low = df["low"] <= df[["open", "close"]].min(axis=1)
    df = df[valid_high & valid_low]

    # One row per symbol/date; retain the last source row for duplicates.
    df = df.drop_duplicates(["symbol", "date"], keep="last")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    today = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()
    future_rows = df["date"] > today
    future_count = int(future_rows.sum())
    if future_count:
        df = df.loc[~future_rows].copy()

    if df.empty:
        raise ValueError("No valid OHLCV rows remain after cleaning. Check symbols, dates and OHLC values.")

    warnings: List[str] = []
    if future_count:
        warnings.append(f"Ignored {future_count} row(s) with future dates.")
    counts = df.groupby("symbol")["date"].nunique()
    short_symbols = counts[counts < MIN_CANDLES]
    if not short_symbols.empty:
        warnings.append(
            f"{len(short_symbols)} symbol(s) have fewer than {MIN_CANDLES} unique daily candles; "
            "they will be marked INSUFFICIENT DATA."
        )

    latest_dates = df.groupby("symbol")["date"].max()
    stale_symbols = latest_dates[latest_dates < today - pd.Timedelta(days=STALE_DAYS)]
    if not stale_symbols.empty:
        warnings.append(
            f"Stale data detected for: {', '.join(stale_symbols.index.astype(str))} "
            f"(latest candle is more than {STALE_DAYS} calendar days old)."
        )

    return df, warnings

# ============================================================
# WEEKLY TREND
# ============================================================
def calculate_weekly_trend(daily: pd.DataFrame) -> Tuple[bool, int, str]:
    weekly = (
        daily.set_index("date")
        .resample("W-FRI")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["close"])
    )

    # Exclude the current incomplete week. This is deliberately conservative.
    if not weekly.empty:
        last_daily_date = pd.Timestamp(daily["date"].iloc[-1])
        if weekly.index[-1] > last_daily_date:
            weekly = weekly.iloc[:-1]

    completed_weeks = len(weekly)
    if completed_weeks < MIN_COMPLETED_WEEKS:
        return False, completed_weeks, f"Need {MIN_COMPLETED_WEEKS} completed weeks; found {completed_weeks}"

    weekly_close = weekly["close"]
    weekly_ema10 = weekly_close.ewm(span=10, adjust=False).mean()
    weekly_ema20 = weekly_close.ewm(span=20, adjust=False).mean()
    is_up = bool(weekly_close.iloc[-1] > weekly_ema10.iloc[-1] > weekly_ema20.iloc[-1])
    return is_up, completed_weeks, "Weekly trend confirmed" if is_up else "Weekly trend is not bullish"

# ============================================================
# SYMBOL ANALYSIS
# ============================================================
def analyze_symbol(group: pd.DataFrame) -> Dict[str, Any]:
    d = group.sort_values("date").drop_duplicates("date").copy()
    symbol = str(d["symbol"].iloc[-1]) if not d.empty else "UNKNOWN"

    if len(d) < MIN_CANDLES:
        return {
            "symbol": symbol,
            "date": pd.Timestamp(d["date"].max()).date().isoformat() if not d.empty else "",
            "close": np.nan,
            "status": "INSUFFICIENT DATA",
            "score": 0,
            "rsi14": np.nan,
            "volume_ratio": np.nan,
            "weekly_uptrend": False,
            "weekly_candles": 0,
            "data_age_days": np.nan,
            "entry_low": np.nan,
            "entry_high": np.nan,
            "stop_loss": np.nan,
            "target_1": np.nan,
            "target_2": np.nan,
            "risk_reward_1": np.nan,
            "risk_reward_2": np.nan,
            "holding_window": f"{HOLD_MIN_DAYS}-{HOLD_MAX_DAYS} trading days",
            "failed_checks": f"Only {len(d)} daily candles available; need {MIN_CANDLES}",
        }

    close = d["close"]
    d["ema20"] = close.ewm(span=20, adjust=False).mean()
    d["ema50"] = close.ewm(span=50, adjust=False).mean()
    d["ema200"] = close.ewm(span=200, adjust=False).mean()
    d["rsi14"] = calculate_rsi(close, RSI_PERIOD)
    d["atr14"] = calculate_atr(d, ATR_PERIOD)
    d["avg_vol20"] = d["volume"].shift(1).rolling(20, min_periods=20).mean()
    d["prior_high20"] = d["high"].shift(1).rolling(BREAKOUT_LOOKBACK, min_periods=BREAKOUT_LOOKBACK).max()

    last = d.iloc[-1]
    prev = d.iloc[-2]

    price = float(last["close"])
    ema20 = float(last["ema20"])
    ema50 = float(last["ema50"])
    ema200 = float(last["ema200"])
    rsi = float(last["rsi14"]) if pd.notna(last["rsi14"]) else np.nan
    atr = float(last["atr14"]) if pd.notna(last["atr14"]) else np.nan
    avg_vol = float(last["avg_vol20"]) if pd.notna(last["avg_vol20"]) else np.nan
    vol_ratio = float(last["volume"]) / avg_vol if np.isfinite(avg_vol) and avg_vol > 0 else np.nan
    resistance = float(last["prior_high20"]) if pd.notna(last["prior_high20"]) else np.nan

    weekly_up, weekly_count, weekly_note = calculate_weekly_trend(d)
    today = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()
    data_age_days = max(0, int((today - pd.Timestamp(last["date"]).normalize()).days))
    data_is_fresh = data_age_days <= STALE_DAYS

    trend = bool(price > ema20 > ema50)
    long_trend = bool(price > ema200)
    momentum = bool(np.isfinite(rsi) and RSI_MIN <= rsi <= RSI_MAX)
    volume_ok = bool(np.isfinite(vol_ratio) and vol_ratio >= MIN_VOLUME_RATIO)
    breakout = bool(np.isfinite(resistance) and price > resistance)
    pullback_reclaim = bool(
        price > ema20
        and pd.notna(prev["ema20"])
        and float(prev["close"]) <= float(prev["ema20"])
    )
    not_extended = bool(np.isfinite(atr) and atr > 0 and price <= ema20 + 2.5 * atr)

    checks = [
        ("Daily uptrend: Price > EMA20 > EMA50", trend),
        ("Above EMA200", long_trend),
        ("Weekly uptrend (40+ completed weeks)", weekly_up),
        (f"RSI in range ({RSI_MIN:.0f}-{RSI_MAX:.0f})", momentum),
        (f"Volume ratio >= {MIN_VOLUME_RATIO:.2f}", volume_ok),
        ("Breakout or pullback reclaim", bool(breakout or pullback_reclaim)),
        ("Not overextended (within 2.5 ATR of EMA20)", not_extended),
    ]

    passed = sum(1 for _, ok in checks if ok)
    score = int(round(100 * passed / len(checks)))

    # Candidate = all seven quality gates. Watchlist is intentionally stricter
    # than a simple score: trend, long trend, weekly trend and RSI must pass.
    candidate = all(ok for _, ok in checks)
    watchlist = (
        not candidate
        and score >= 85
        and trend
        and long_trend
        and weekly_up
        and momentum
        and not_extended
    )
    if not data_is_fresh:
        status = "STALE DATA"
    elif candidate:
        status = "SWING CANDIDATE"
    elif watchlist:
        status = "WATCHLIST"
    else:
        status = "REJECT"

    # ATR-based indicative levels. These are estimates, not executable orders.
    if np.isfinite(atr) and atr > 0:
        entry_low_raw = max(TICK_SIZE, price - 0.25 * atr)
        entry_high_raw = price + 0.25 * atr
        risk_per_share = min(max(1.5 * atr, price * 0.04), price * 0.10)
    else:
        entry_low_raw = price * 0.99
        entry_high_raw = price * 1.01
        risk_per_share = price * 0.06

    entry_low = round_to_tick(entry_low_raw)
    entry_high = round_to_tick(entry_high_raw)
    entry_mid = (entry_low + entry_high) / 2.0
    stop = round_to_tick(max(TICK_SIZE, entry_mid - risk_per_share))
    actual_risk = entry_mid - stop
    target1 = round_to_tick(entry_mid + 2.0 * actual_risk)
    target2 = round_to_tick(entry_mid + 3.0 * actual_risk)

    # Guard against rounding collapsing the risk or creating invalid levels.
    levels_valid = bool(
        np.isfinite(actual_risk)
        and actual_risk > 0
        and stop < entry_mid < target1 < target2
        and entry_low <= entry_high
    )
    rr1 = (target1 - entry_mid) / actual_risk if levels_valid else np.nan
    rr2 = (target2 - entry_mid) / actual_risk if levels_valid else np.nan

    failed = [label for label, ok in checks if not ok]
    if weekly_count < MIN_COMPLETED_WEEKS:
        failed.append(weekly_note)
    if not levels_valid:
        failed.append("Risk level calculation failed")

    return {
        "symbol": symbol,
        "date": pd.Timestamp(last["date"]).date().isoformat(),
        "close": round(price, 2),
        "status": status if levels_valid else "REJECT",
        "score": score,
        "rsi14": round(rsi, 1) if np.isfinite(rsi) else np.nan,
        "volume_ratio": round(vol_ratio, 2) if np.isfinite(vol_ratio) else np.nan,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "weekly_uptrend": weekly_up,
        "weekly_candles": weekly_count,
        "data_age_days": data_age_days,
        "breakout20": breakout,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop,
        "target_1": target1,
        "target_2": target2,
        "risk_reward_1": round(rr1, 2) if np.isfinite(rr1) else np.nan,
        "risk_reward_2": round(rr2, 2) if np.isfinite(rr2) else np.nan,
        "holding_window": f"{HOLD_MIN_DAYS}-{HOLD_MAX_DAYS} trading days",
        "failed_checks": ", ".join(failed) if failed else "All seven quality checks passed",
    }

# ============================================================
# SCANNER
# ============================================================
def scan_universe(df: pd.DataFrame) -> pd.DataFrame:
    rows = [analyze_symbol(group) for _, group in df.groupby("symbol", sort=True)]
    result = pd.DataFrame(rows)
    if result.empty:
        return result

    status_order = {"SWING CANDIDATE": 0, "WATCHLIST": 1, "REJECT": 2, "STALE DATA": 3, "INSUFFICIENT DATA": 4}
    result["_order"] = result["status"].map(status_order).fillna(9)
    result = result.sort_values(
        ["_order", "score", "rsi14"],
        ascending=[True, False, True],
        na_position="last",
    ).drop(columns="_order")
    return result.reset_index(drop=True)

# ============================================================
# USER INTERFACE
# ============================================================
st.markdown("# 📈 SWIFT TRADE — PROFESSIONAL SWING SCANNER")
st.caption(
    "Offline CSV Edition • Daily + Weekly Trend Filters • "
    f"Holding window: {HOLD_MIN_DAYS}-{HOLD_MAX_DAYS} trading days"
)

st.warning(
    "This scanner does not fetch live or historical prices from the internet. "
    "Upload genuine historical daily OHLCV CSV data. Never use synthetic/demo data for live trading decisions."
)

with st.expander("Required CSV Format", expanded=False):
    st.code(
        "symbol,date,open,high,low,close,volume\n"
        "RELIANCE,2025-01-02,2450.00,2478.50,2435.00,2465.25,1850000\n"
        "TCS,2025-01-02,3850.00,3890.00,3835.50,3872.00,920000"
    )
    st.write(
        "• One row per symbol per trading day\n"
        f"• At least {MIN_CANDLES} daily candles per symbol\n"
        f"• At least {MIN_COMPLETED_WEEKS} completed weekly candles for weekly trend confirmation\n"
        f"• Latest candle must be no more than {STALE_DAYS} calendar days old"
    )

uploaded = st.file_uploader("Upload Historical Daily OHLCV CSV", type=["csv"])
if uploaded is None:
    st.info("No data loaded. Upload a genuine historical CSV to start scanning.")
    st.stop()

try:
    raw_data = pd.read_csv(uploaded)
    market_data, data_warnings = normalize_upload(raw_data)
except Exception as exc:
    st.error(f"CSV validation failed: {exc}")
    st.stop()

for warning in data_warnings:
    st.warning(warning)

try:
    results = scan_universe(market_data)
except Exception as exc:
    st.error(f"Scanner failed while analyzing the uploaded data: {exc}")
    st.stop()

if results.empty:
    st.error("No symbols could be analyzed from this CSV.")
    st.stop()

# Summary metrics
metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Symbols Loaded", int(market_data["symbol"].nunique()))
metric2.metric("Total Daily Rows", int(len(market_data)))
metric3.metric("Swing Candidates", int((results["status"] == "SWING CANDIDATE").sum()))
metric4.metric("Watchlist", int((results["status"] == "WATCHLIST").sum()))

# Top six only
st.subheader(f"Top Swing Setups (Maximum {TOP_N})")
candidates = results[results["status"].isin(["SWING CANDIDATE", "WATCHLIST"])].head(TOP_N)
if candidates.empty:
    st.info("No symbols currently pass the quality filters. Do not loosen rules just to force signals.")
else:
    candidate_columns = [
        "symbol", "status", "score", "close", "rsi14", "volume_ratio",
        "entry_low", "entry_high", "stop_loss", "target_1", "target_2",
        "risk_reward_1", "risk_reward_2", "data_age_days", "holding_window",
    ]
    st.dataframe(candidates[candidate_columns], use_container_width=True, hide_index=True)

# Full results
with st.expander("Full Scan Results", expanded=False):
    st.dataframe(results, use_container_width=True, hide_index=True)

# Rejection explanation
st.subheader("Why a Symbol Did Not Qualify")
selected_symbol = st.selectbox("Select Symbol", results["symbol"].tolist())
selected_row = results.loc[results["symbol"] == selected_symbol].iloc[0]
st.write(selected_row.get("failed_checks", "No additional details available."))

# Download
st.download_button(
    label="Download Full Scan Results (CSV)",
    data=results.to_csv(index=False).encode("utf-8"),
    file_name="swift_trade_swing_scan_results.csv",
    mime="text/csv",
)

st.caption(
    "Research and testing tool only. Entry, stop and target levels are rule-based estimates, not guaranteed outcomes. "
    "Review liquidity, corporate actions, earnings, slippage, position sizing and historical performance before trading."
)
