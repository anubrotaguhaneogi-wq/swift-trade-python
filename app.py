# ============================== PART 1/4 ==============================
# CONFIGURATION, UNIVERSE, MARKET CALENDAR, DATA ENGINE
from __future__ import annotations

import math
import time
from datetime import date, datetime, time as dtime, timedelta
from typing import Dict, Optional, Tuple, List

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

try:
    import pandas_market_calendars as mcal
    HAS_NSE_CALENDAR = True
except Exception:
    mcal = None
    HAS_NSE_CALENDAR = False

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except Exception:
    st_autorefresh = None
    HAS_AUTOREFRESH = False

APP_TITLE = "Swift Trade V5 | Dynamic Scanner"
IST = "Asia/Kolkata"
EXCHANGE_TZ = IST

TOP_N = 6
TICK_SIZE = 0.05
RESISTANCE_LOOKBACK_DAYS = 20
VOLUME_LOOKBACK_DAYS = 10
EMA_FAST = 9
EMA_MID = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14

MIN_1H_BARS = 60
MIN_15M_BARS = 60
MIN_5M_BARS = 30
MAX_LIVE_AGE_MIN = 7
MAX_SIGNAL_AGE_MIN = 22
MAX_PRICE_DEVIATION_PCT = 5.0

MAX_EXTENSION_PCT = 2.0
NEAR_DISTANCE_PCT = 1.0
MIN_VOLUME_RATIO = 1.30
RSI_MIN_BUY = 48.0
RSI_MAX_BUY = 72.0
MAX_ENTRY_RISK_PCT = 2.5
ATR_STOP_MULTIPLIER = 1.5
REWARD_RISK = 2.0
ENTRY_CUTOFF = dtime(14, 30)
MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)

# Yahoo Finance intraday retention is limited. Periods are deliberately conservative.
YF_PERIODS = {"1m": "2d", "5m": "5d", "15m": "1mo", "1h": "3mo", "1d": "6mo"}

SECTORS = {
    "Bank": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK", "FEDERALBNK"],
    "IT": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "PERSISTENT", "COFORGE"],
    "Auto": ["MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO", "ASHOKLEY", "TVSMOTOR"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA", "BIOCON"],
    "Energy": ["RELIANCE", "ONGC", "COALINDIA", "NTPC", "POWERGRID", "BPCL", "IOC"],
    "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "TATACONSUM"],
    "Metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC", "SAIL", "JINDALSTEL"],
    "PSU & Defence": ["BEL", "HAL", "IRFC", "RVNL", "RECLTD", "PFC", "BHEL", "MAZDOCK", "BDL"],
    "Others": ["ASIANPAINT", "TITAN", "TRENT", "ADANIENT", "ETERNAL", "PAYTM", "POLYCAB", "DIXON", "LT", "ULTRACEMCO"],
}
INDEX_SYMBOLS = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "SENSEX": "^BSESN", "INDIA VIX": "^INDIAVIX"}
INTERVAL_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
OHLCV = ["Open", "High", "Low", "Close", "Volume"]

st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")


def now_ist() -> pd.Timestamp:
    return pd.Timestamp.now(tz=IST)


def to_ist_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Yahoo intraday timestamps are treated as exchange-local when tz-aware.
    Naive timestamps are localized to IST; this avoids silently treating local
    exchange timestamps as UTC.
    """
    if frame is None or frame.empty:
        return pd.DataFrame(columns=OHLCV)
    out = frame.copy()
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is None:
        idx = idx.tz_localize(IST)
    else:
        idx = idx.tz_convert(IST)
    out.index = idx
    return out.sort_index()


def clean_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=OHLCV)
    df = frame.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        return pd.DataFrame(columns=OHLCV)
    df = df[OHLCV].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df["Volume"] = df["Volume"].fillna(0).clip(lower=0)
    
    price_cols = ["Open", "High", "Low", "Close"]

    finite_prices = np.isfinite(df[price_cols]).all(axis=1)
    positive_prices = (df[price_cols] > 0).all(axis=1)

    valid_ohlc = (
        (df["High"] >= df[["Open", "Close"]].max(axis=1))
        & (df["Low"] <= df[["Open", "Close"]].min(axis=1))
        & (df["High"] >= df["Low"])
    )

    df = df.loc[
        finite_prices & positive_prices & valid_ohlc
    ].copy()

    if df.empty:
        return df
        
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def _extract_symbol(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=OHLCV)
    if isinstance(raw.columns, pd.MultiIndex):
        # yfinance column order may be (Price, Ticker) or (Ticker, Price).
        if ticker in raw.columns.get_level_values(-1):
            part = raw.xs(ticker, axis=1, level=-1, drop_level=True)
        elif ticker in raw.columns.get_level_values(0):
            part = raw.xs(ticker, axis=1, level=0, drop_level=True)
        else:
            return pd.DataFrame(columns=OHLCV)
    else:
        part = raw
    return clean_ohlcv(part)


@st.cache_data(ttl=90, show_spinner=False)
def download_market_data(symbols: Tuple[str, ...], interval: str, period: str, cache_bucket: int):
    """Download one interval for all requested NSE symbols."""
    if not symbols:
        return {}
    tickers = [s if s.startswith("^") else f"{s}.NS" for s in symbols]
    try:
        raw = yf.download(
            tickers=tickers, period=period, interval=interval,
            group_by="ticker", auto_adjust=False, actions=False,
            progress=False, threads=True, prepost=False,
        )
    except Exception as exc:
        return {"__ERROR__": str(exc)}
    if raw is None or raw.empty:
        return {"__ERROR__": f"No Yahoo data returned for interval {interval}"}
    result = {}
    for symbol, ticker in zip(symbols, tickers):
        try:
            part = _extract_symbol(raw, ticker)
            if not part.empty:
                part = to_ist_frame(part)
                result[symbol] = part
        except Exception:
            continue
    return result


def fetch_interval(symbols: List[str], interval: str):
    period = YF_PERIODS[interval]
    # cache bucket changes at the interval boundary; TTL remains a secondary guard.
    seconds = INTERVAL_MINUTES[interval] * 60
    bucket = int(time.time() // seconds)
    return download_market_data(tuple(symbols), interval, period, bucket)


def market_calendar_status(day: date) -> Tuple[bool, str]:
    """Return (is_session, explanation). A calendar fallback is explicitly flagged."""
    if not HAS_NSE_CALENDAR:
        return day.weekday() < 5, "NSE holiday calendar package unavailable; weekday-only fallback"
    try:
        cal = mcal.get_calendar("NSE")
        schedule = cal.schedule(start_date=day.isoformat(), end_date=day.isoformat())
        return not schedule.empty, "NSE exchange calendar"
    except Exception as exc:
        return day.weekday() < 5, f"Calendar lookup failed; weekday-only fallback ({exc})"


def completed_candles(frame: pd.DataFrame, interval: str, current: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """Keep only bars whose expected end time has passed.
    Yahoo timestamps are assumed to mark candle start. This assumption must be
    checked against the live Yahoo feed before relying on minute-level execution.
    """
    if frame is None or frame.empty:
        return pd.DataFrame(columns=OHLCV)
    current = current or now_ist()
    df = to_ist_frame(frame)
    minutes = INTERVAL_MINUTES[interval]
    idx = pd.DatetimeIndex(df.index)
    ends = idx + pd.Timedelta(minutes=minutes)
    session_close = idx.normalize() + pd.Timedelta(hours=15, minutes=30)
    ends = pd.DatetimeIndex([min(e, c) if e.date() == c.date() else e for e, c in zip(ends, session_close)])
    return df.loc[ends <= current].copy()


def last_price_from_intraday(frames: Dict[str, pd.DataFrame]) -> Tuple[Optional[float], Optional[pd.Timestamp], str]:
    candidates = []
    now = now_ist()
    for interval in ("1m", "5m", "15m"):
        df = frames.get(interval)
        if df is None or df.empty:
            continue
        d = to_ist_frame(df)
        today = d[d.index.date == now.date()]
        if today.empty:
            continue
         valid_today = today[today.index <= now]
        if valid_today.empty:
            continue
        ts = valid_today.index[-1]
        px = float(valid_today["Close"].iloc[-1])
        
        
        if np.isfinite(px) and px > 0:
            candidates.append((ts, px, interval))
    if not candidates:
        return None, None, "Unavailable"
    ts, px, interval = max(candidates, key=lambda x: x[0])
    return px, ts, interval


@st.cache_data(ttl=60, show_spinner=False)
def download_indices(bucket: int):
    out = {}
    for name, ticker in INDEX_SYMBOLS.items():
        try:
            raw = yf.download(ticker, period="5d", interval="1d", auto_adjust=False, progress=False)
            if raw is None or raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            close = pd.to_numeric(raw["Close"], errors="coerce").dropna()
            if len(close) >= 2:
                last, prev = float(close.iloc[-1]), float(close.iloc[-2])
                out[name] = {"price": last, "change": last - prev, "pct": (last / prev - 1) * 100 if prev else 0}
        except Exception:
            continue
    return out
# ============================== PART 2/4 ==============================
# INDICATORS, MARKET CONTEXT, TREND / BREAKOUT / CONFIRMATION ANALYSIS

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    value = 100 - (100 / (1 + rs))
    value = value.mask((avg_loss == 0) & (avg_gain > 0), 100)
    value = value.mask((avg_gain == 0) & (avg_loss > 0), 0)
    value = value.mask((avg_gain == 0) & (avg_loss == 0), 50)
    return value.fillna(50)


def atr(frame: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    prev_close = frame["Close"].shift(1)
    tr = pd.concat([
        frame["High"] - frame["Low"],
        (frame["High"] - prev_close).abs(),
        (frame["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def same_slot_volume_ratio(frame: pd.DataFrame, breakout_ts: pd.Timestamp, lookback_days: int = VOLUME_LOOKBACK_DAYS) -> float:
    """Compare breakout bar volume with median volume at the same 15m time slot
    across preceding sessions. Never substitute a zero/NaN ratio with a pass.
    """
    if frame is None or frame.empty or breakout_ts not in frame.index:
        return float("nan")
    df = to_ist_frame(frame)
    slot = breakout_ts.strftime("%H:%M")
    prior = df[(df.index.date < breakout_ts.date()) & (df.index.strftime("%H:%M") == slot)].tail(lookback_days)
    if len(prior) < 3:
        return float("nan")
    baseline = float(prior["Volume"].median())
    current_volume = float(df.loc[breakout_ts, "Volume"])
    if baseline <= 0:
        return float("nan")
    return current_volume / baseline


def market_context() -> Dict[str, object]:
    now = now_ist()
    is_session, calendar_note = market_calendar_status(now.date())
    t = now.time()
    if not is_session:
        phase = "CLOSED"
        message = "আজ NSE ট্রেডিং সেশন নেই।"
    elif t < MARKET_OPEN:
        phase = "PREOPEN"
        message = "বাজার খোলেনি।"
    elif t >= MARKET_CLOSE:
        phase = "CLOSED"
        message = "বাজার বন্ধ।"
    elif t < dtime(9, 30):
        phase = "EARLY"
        message = "প্রথম ১৫ মিনিটে নতুন এন্ট্রি এড়ানো হচ্ছে।"
    elif t >= ENTRY_CUTOFF:
        phase = "NO_NEW_ENTRY"
        message = "নতুন BUY entry cutoff পেরিয়ে গেছে; বিদ্যমান সেটআপ শুধু পর্যবেক্ষণ করুন।"
    else:
        phase = "OPEN"
        message = ""
    return {"phase": phase, "message": message, "calendar_note": calendar_note, "now": now}


def index_market_filter(index_data: Dict[str, dict]) -> Tuple[bool, str]:
    """Conservative broad-market guard. Daily change is context, not intraday trend."""
    nifty = index_data.get("NIFTY 50")
    if not nifty:
        return True, "NIFTY data unavailable; market filter not applied"
    pct = float(nifty.get("pct", 0.0))
    if pct <= -1.5:
        return False, f"NIFTY daily change {pct:.2f}%: broad-market risk is high"
    return True, f"NIFTY daily change {pct:+.2f}%"


def analyze_stock(symbol: str, sector: str, data: Dict[str, pd.DataFrame],
                  context: Dict[str, object], market_ok: bool, market_note: str):
    daily_raw = data.get("1d")
    h1_raw = data.get("1h")
    m15_raw = data.get("15m")
    m5_raw = data.get("5m")
    m1_raw = data.get("1m")

    if any(x is None or x.empty for x in (daily_raw, h1_raw, m15_raw, m5_raw)):
        return None, "Required timeframe data missing"

    now = context["now"]
    daily = daily_raw.copy()
    daily.index = pd.DatetimeIndex(daily.index).tz_localize(None).normalize() if pd.DatetimeIndex(daily.index).tz is not None else pd.DatetimeIndex(daily.index).normalize()
    h1 = completed_candles(h1_raw, "1h", now)
    m15 = completed_candles(m15_raw, "15m", now)
    m5 = completed_candles(m5_raw, "5m", now)

    if len(h1) < MIN_1H_BARS or len(m15) < MIN_15M_BARS or len(m5) < MIN_5M_BARS:
        return None, f"Insufficient candles: 1H={len(h1)}, 15M={len(m15)}, 5M={len(m5)}"

    session_date = now.date()
    prior_daily = daily[daily.index.date < session_date]
    if len(prior_daily) < RESISTANCE_LOOKBACK_DAYS + 1:
        return None, "Insufficient completed daily history"

    resistance = float(prior_daily["High"].tail(RESISTANCE_LOOKBACK_DAYS).max())
    prev_close = float(prior_daily["Close"].iloc[-1])
    if not np.isfinite(resistance) or resistance <= 0:
        return None, "Invalid resistance"

    # 1H trend: only completed hourly candles.
    h1 = h1.copy()
    h1["ema20"] = ema(h1["Close"], EMA_MID)
    h1["ema50"] = ema(h1["Close"], EMA_SLOW)
    h1_last = h1.iloc[-1]
    trend_up = bool(h1_last["Close"] > h1_last["ema20"] > h1_last["ema50"])
    trend_down = bool(h1_last["Close"] < h1_last["ema20"] < h1_last["ema50"])

    # 15M breakout and same-time-of-day relative volume.
    m15 = m15.copy()
    m15["rsi"] = rsi(m15["Close"])
    m15["atr"] = atr(m15)
    today15 = m15[m15.index.date == session_date]
    if today15.empty:
        return None, "No completed 15M candle for current session"
    last15 = today15.iloc[-1]
    sig_ts = today15.index[-1]
    signal_close = float(last15["Close"])
    rsi_value = float(last15["rsi"])
    atr_value = float(last15["atr"]) if pd.notna(last15["atr"]) else float("nan")
    breakout = signal_close > resistance
                          # Track the latest genuine 15M breakout crossing in today's session.
    previous_close = m15["Close"].shift(1)
    first_today = m15.index.date == session_date
    first_today_bar = first_today & ~pd.Series(first_today, index=m15.index).shift(1, fill_value=False)

    crossed_above = (
        (m15["Close"] > resistance)
        & (
            (previous_close <= resistance)
            | (first_today_bar & (m15["Open"] > resistance))
        )
        & first_today
    )

    today_crosses = m15.loc[crossed_above]
    signal_start_ts = None
    if breakout and not today_crosses.empty:
        signal_start_ts = today_crosses.index[-1]
        signal_age_min = max(
            0.0,
            (now - (signal_start_ts + pd.Timedelta(minutes=15))).total_seconds() / 60.0
        )
    elif breakout:
        signal_age_min = float("inf")
    else:
        signal_age_min = 0.0

    signal_fresh = (not breakout) or signal_age_min <= MAX_SIGNAL_AGE_MIN
    volume_ratio = (
    same_slot_volume_ratio(m15, signal_start_ts)
    if breakout and signal_start_ts is not None
    else float("nan")
    )
    volume_ok = bool(np.isfinite(volume_ratio) and volume_ratio >= MIN_VOLUME_RATIO)
    # 5M confirmation uses multi-day history for EMA warm-up
    m5 = m5.copy()
    m5["ema9"] = ema(m5["Close"], EMA_FAST)
    today5 = m5[m5.index.date == session_date]

    if len(today5) >= 2:
        last5 = today5.iloc[-1]
        confirm5 = bool(
            last5["Close"] > resistance
            and last5["Close"] > last5["ema9"]
        )
    else:
        confirm5 = False

    live_price, live_ts, live_interval = last_price_from_intraday({"1m": m1_raw, "5m": m5_raw, "15m": m15_raw})
    if live_price is None or live_ts is None:
        live_price, live_ts, live_interval = signal_close, sig_ts, "15M fallback"
    age_min = max(0.0, (now - live_ts).total_seconds() / 60.0)
    deviation = abs(live_price / signal_close - 1) * 100 if signal_close else 999
    stale = age_min > MAX_LIVE_AGE_MIN or deviation > MAX_PRICE_DEVIATION_PCT
    if deviation > MAX_PRICE_DEVIATION_PCT:
        live_price = signal_close

    extension_pct = (live_price / resistance - 1) * 100
    change_pct = (live_price / prev_close - 1) * 100 if prev_close else 0.0
    near = -NEAR_DISTANCE_PCT <= extension_pct <= 0
    gap_up = float(today15["Open"].iloc[0]) > resistance * 1.003

    # Status engine: a downtrend breakout is visible as CAUTION, not silently discarded.
    
    if stale:
        status, note = "WAIT", f"Price data stale or inconsistent ({age_min:.1f} min; deviation {deviation:.2f}%)."
    elif context["phase"] in ("CLOSED", "PREOPEN"):
        status, note = ("AVOID" if trend_down else "WAIT"), "Market is not in an active trading session."
    elif context["phase"] in ("NO_NEW_ENTRY", "EARLY"):
        status, note = ("AVOID" if trend_down else "WAIT"), str(context["message"])
    elif breakout and not signal_fresh:
        status, note = "WAIT", (
            f"Breakout signal expired ({signal_age_min:.1f} min). "
            "Wait for a fresh breakout."
        )
    elif breakout and live_price <= resistance:
        status, note = "WAIT", "Breakout failed: live price is back below resistance. No BUY entry."
    elif breakout and trend_down:
        status, note = "CAUTION", "15M breakout against the 1H downtrend. Counter-trend trade is not approved."
    elif breakout and (extension_pct > MAX_EXTENSION_PCT or rsi_value > RSI_MAX_BUY):
        status, note = "LATE", "Breakout is extended or RSI is above the approved entry zone."
    elif breakout and not volume_ok:
        status, note = "WAIT", "Breakout volume is insufficient or historical same-slot baseline is unavailable."
    elif breakout and gap_up and not confirm5:
        status, note = "TRIGGER", "Gap-up breakout; wait for 5M hold and confirmation."
    elif breakout and trend_up and confirm5 and RSI_MIN_BUY <= rsi_value <= RSI_MAX_BUY:
        status, note = "BUY", "1H trend, 15M breakout/volume, 5M confirmation and RSI aligned."
    elif breakout:
        status, note = "TRIGGER", "Breakout detected; waiting for all confirmation conditions."
    elif near and trend_up and extension_pct <= 0:
        status, note = "NEAR", "Price is near resistance; wait for a completed 15M breakout."
    elif trend_down:
        status, note = "AVOID", "1H trend is down."
    else:
        status, note = "WAIT", "No qualified breakout setup."
        

    if not market_ok and status in ("BUY", "TRIGGER", "NEAR"):
        status, note = "WAIT", f"No confirmed NSE session: {market_note}"
    if not market_ok and trend_down:
        status = "AVOID"

    # PART 3 completes risk and ranking fields.
    return {
        "symbol": symbol, "sector": sector, "status": status, "note": note,
        "price": float(live_price), "price_time": live_ts.strftime("%H:%M:%S"),
        "price_age_min": round(age_min, 1), "resistance": resistance,
        "extension_pct": extension_pct, "change_pct": change_pct,
        "rsi": rsi_value, "atr": atr_value, "volume_ratio": volume_ratio,
        "trend_up": trend_up, "trend_down": trend_down, "breakout": breakout,
        "volume_ok": volume_ok, "confirm5": confirm5, "gap_up": gap_up,
        "signal_time": sig_ts.strftime("%H:%M"), "stale": stale,
                "signal_age_min": round(signal_age_min, 1) if np.isfinite(signal_age_min) else None,
        "signal_fresh": signal_fresh,
    }, None
      # ============================== PART 3/4 ==============================
# ENTRY / STOP / TARGET, RISK FILTER, RANKING, SCAN ORCHESTRATION

STATUS_ORDER = {"BUY": 0, "TRIGGER": 1, "NEAR": 2, "CAUTION": 3, "LATE": 4, "WAIT": 5, "AVOID": 6}


def round_tick(value: float, tick: float = TICK_SIZE) -> float:
    if not np.isfinite(value):
        return float("nan")
    return round(round(value / tick) * tick, 2)


def apply_risk_and_score(row: dict) -> dict:
    entry = float(row["price"])
    resistance = float(row["resistance"])
    atr_value = row["atr"]
    if not np.isfinite(atr_value) or atr_value <= 0:
        atr_value = entry * 0.01

    # Structural stop: below resistance with ATR buffer; never tighten a stop
    # merely to satisfy the risk cap. If risk is too large, downgrade the setup.
    stop = min(resistance - 0.5 * atr_value, entry - ATR_STOP_MULTIPLIER * atr_value)
    if stop <= 0 or stop >= entry:
        stop = entry - ATR_STOP_MULTIPLIER * atr_value
    risk_pct = (entry - stop) / entry * 100 if entry > 0 else 999.0
    target = entry + REWARD_RISK * (entry - stop)

    if risk_pct > MAX_ENTRY_RISK_PCT and row["status"] == "BUY":
        row["status"] = "WAIT"
        row["note"] = f"Structural stop requires {risk_pct:.2f}% risk; above {MAX_ENTRY_RISK_PCT:.2f}% limit. No entry."
    if row["status"] == "BUY" and row["price"] > resistance * (1 + MAX_EXTENSION_PCT / 100):
        row["status"] = "LATE"
        row["note"] = "Price moved beyond maximum extension before entry."

    row.update({
        "entry": round_tick(entry),
        "stop_loss": round_tick(stop),
        "target": round_tick(target),
        "risk_pct": round(risk_pct, 2),
        "reward_risk": REWARD_RISK,
    })

    vol_score = min(float(row["volume_ratio"]), 4.0) if np.isfinite(row["volume_ratio"]) else 0.0
    rsi_score = 1.0 if RSI_MIN_BUY <= row["rsi"] <= RSI_MAX_BUY else 0.0
    row["score"] = (
        vol_score * 2.0
        + (1.5 if row["trend_up"] else 0.0)
        + (1.5 if row["confirm5"] else 0.0)
        + rsi_score
        - max(0.0, row["extension_pct"]) * 0.5
        - max(0.0, row["price_age_min"] - 2) * 0.1
    )
    return row


def build_symbol_sector(selected_sectors: List[str]) -> Dict[str, str]:
    mapping = {}
    for sector in selected_sectors:
        for symbol in SECTORS.get(sector, []):
            mapping.setdefault(symbol, sector)
    return mapping


def scan_market(selected_sectors: List[str], force_refresh: bool = False):
    mapping = build_symbol_sector(selected_sectors)
    symbols = list(mapping)
    if not symbols:
        return [], [("Universe", "No stocks selected.")], {}

    if force_refresh:
        download_market_data.clear()
        download_indices.clear()

    progress = st.progress(0, text="Downloading daily data...")
    data_by_interval = {}
    intervals = ["1d", "1h", "15m", "5m", "1m"]
    for i, interval in enumerate(intervals):
        data_by_interval[interval] = fetch_interval(symbols, interval)
        progress.progress(int((i + 1) / len(intervals) * 45), text=f"Downloading {interval} data...")

    indices = download_indices(int(time.time() // 60))
    market_ok, market_note = index_market_filter(indices)
    context = market_context()
    progress.progress(55, text="Analyzing symbols...")

    rows, skipped = [], []
    for i, symbol in enumerate(symbols):
        data = {tf: data_by_interval.get(tf, {}).get(symbol) for tf in intervals}
        # Ignore download-level errors and let analyze explain missing symbol data.
        try:
            row, reason = analyze_stock(symbol, mapping[symbol], data, context, market_ok, market_note)
            if row:
                rows.append(apply_risk_and_score(row))
            else:
                skipped.append((symbol, reason or "No setup"))
        except Exception as exc:
            skipped.append((symbol, f"Analysis error: {exc}"))
        progress.progress(55 + int((i + 1) / len(symbols) * 45), text=f"Analyzing {symbol}...")
    progress.empty()

    rows.sort(key=lambda r: (STATUS_ORDER.get(r["status"], 99), -r["score"]))
    eligible = [r for r in rows if r["status"] in ("BUY", "TRIGGER")]
    picks = eligible[:TOP_N]
    return picks, skipped, {"rows": rows, "indices": indices, "context": context, "market_note": market_note}
  
# ============================== PART 4/4 ==============================
# STREAMLIT DASHBOARD, FILTERS, REFRESH, DISPLAY, EXPORT

def money(value):
    return f"₹{value:,.2f}" if pd.notna(value) else "—"


def render_index_cards(indices: dict):
    if not indices:
        st.warning("Index data unavailable from Yahoo Finance.")
        return
    cols = st.columns(len(indices))
    for col, (name, item) in zip(cols, indices.items()):
        with col:
            st.metric(name, f"{item['price']:,.2f}", f"{item['pct']:+.2f}%")


def render_stock_card(row: dict, rank: int):
    color = {
        "BUY": "#00c853", "TRIGGER": "#ffca28", "NEAR": "#29b6f6",
        "CAUTION": "#ff9800", "LATE": "#fb8c00", "WAIT": "#90a4ae", "AVOID": "#ef5350"
    }.get(row["status"], "#90a4ae")
    st.markdown(f"""
    <div style="border:1px solid #29415c;border-left:5px solid {color};border-radius:12px;padding:14px;margin-bottom:12px;background:#101d2d;">
      <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;">
        <div><span style="color:#9fb3c8;">#{rank}</span> <b style="font-size:1.15rem;color:#fff;">{row['symbol']}</b>
        <div style="color:#91a4b8;font-size:.78rem;">{row['sector']}</div></div>
        <div style="text-align:right;"><b style="font-size:1.1rem;color:#fff;">{money(row['price'])}</b>
        <div style="font-size:.78rem;color:#9fb3c8;">{row['price_time']} IST · age {row['price_age_min']}m</div></div>
      </div>
      <div style="margin:10px 0;color:{color};font-weight:800;">{row['status']}</div>
      <div style="display:flex;gap:7px;flex-wrap:wrap;font-size:.78rem;color:#dce6f0;margin-bottom:10px;">
        <span>1H Trend: {'✅' if row['trend_up'] else '❌'}</span>
        <span>15M Breakout: {'✅' if row['breakout'] else '❌'}</span>
        <span>Volume: {row['volume_ratio']:.2f}x</span>
        <span>5M Confirm: {'✅' if row['confirm5'] else '❌'}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px;">
        <div style="background:#0a1522;padding:8px;border-radius:7px;"><small>ENTRY</small><br><b>{money(row['entry'])}</b></div>
        <div style="background:#0a1522;padding:8px;border-radius:7px;"><small>STOP LOSS</small><br><b style="color:#ff8a80;">{money(row['stop_loss'])}</b></div>
        <div style="background:#0a1522;padding:8px;border-radius:7px;"><small>TARGET</small><br><b style="color:#69f0ae;">{money(row['target'])}</b></div>
      </div>
      <div style="margin-top:9px;color:#b7c7d8;font-size:.78rem;">
        Resistance: {money(row['resistance'])} · RSI: {row['rsi']:.1f} · Risk: {row['risk_pct']:.2f}% · Score: {row['score']:.2f}
      </div>
              <div style="margin-top:7px;color:#b7c7d8;font-size:.78rem;">Signal Age: {row.get('signal_age_min') if row.get('signal_age_min') is not None else 'N/A'} min | Fresh: {'YES' if row.get('signal_fresh', False) else 'NO'}</div>
      <div style="margin-top:7px;color:#e0e8f0;font-size:.82rem;">{row['note']}</div>
    </div>
    """, unsafe_allow_html=True)


def main():
    st.title("📈 Swift Trade V5")
    st.caption("Dynamic NSE Multi-Timeframe Scanner · 1H Trend · 15M Breakout · 5M Confirmation · 1M Price Check")

    st.image("swift_trade_banner.png", use_container_width=True)
    
    context = market_context()
    if context["message"]:
        st.info(context["message"])
    st.caption(f"Calendar: {context['calendar_note']}")

    with st.sidebar:
        st.subheader("Scanner Settings")
        selected_sectors = st.multiselect("Select sectors", list(SECTORS), default=list(SECTORS))
        auto_refresh = st.toggle("Auto refresh (2 minutes)", value=False)
        show_all = st.toggle("Show all analyzed stocks", value=False)
        run_button = st.button("🚀 RUN SCAN", type="primary", use_container_width=True)
        st.caption("Yahoo Finance data may be delayed, incomplete, or revised. Do not treat it as broker execution data.")

    if auto_refresh and HAS_AUTOREFRESH:
        st_autorefresh(interval=120_000, key="swift_trade_v5_refresh")
        run_button = True
    elif auto_refresh and not HAS_AUTOREFRESH:
        st.warning("Install streamlit-autorefresh to enable automatic refresh.")

    if "v5_last_scan" not in st.session_state:
        st.session_state["v5_last_scan"] = None
    if "v5_last_run" not in st.session_state:
        st.session_state["v5_last_run"] = 0.0

    if run_button or st.session_state["v5_last_scan"] is None:
        picks, skipped, meta = scan_market(selected_sectors, force_refresh=run_button)
        st.session_state["v5_last_scan"] = {"picks": picks, "skipped": skipped, "meta": meta}
        st.session_state["v5_last_run"] = time.time()

    result = st.session_state["v5_last_scan"]
    meta = result["meta"]
    render_index_cards(meta.get("indices", {}))

    st.markdown("---")
    all_rows = meta.get("rows", [])
    picks = result["picks"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Analyzed", len(all_rows))
    c2.metric("Top picks", len(picks))
    c3.metric("BUY", sum(r["status"] == "BUY" for r in all_rows))
    c4.metric("AVOID", sum(r["status"] == "AVOID" for r in all_rows))
    st.caption(f"Last scan: {now_ist().strftime('%H:%M:%S')} IST · Data source: Yahoo Finance")

    if not picks:
        st.warning("No qualified stocks found. Do not force a trade; wait for a valid setup.")
    else:
        st.subheader(f"Top {len(picks)} ranked setups")
        for i, row in enumerate(picks, 1):
            render_stock_card(row, i)

    if show_all and all_rows:
        st.subheader("All analyzed stocks")
        table_rows = []
        for r in all_rows:
            table_rows.append({
                "Symbol": r["symbol"], "Sector": r["sector"], "Status": r["status"],
                "Price": r["price"], "Resistance": r["resistance"], "RSI": r["rsi"],
                "Volume x": r["volume_ratio"], "Risk %": r["risk_pct"],
                "Entry": r["entry"], "Stop Loss": r["stop_loss"], "Target": r["target"],
                "Score": r["score"], "Reason": r["note"],
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    if all_rows:
        export_df = pd.DataFrame([{
            "Symbol": r["symbol"], "Sector": r["sector"], "Status": r["status"],
            "Price": r["price"], "Resistance": r["resistance"], "RSI": r["rsi"],
            "Volume_Ratio": r["volume_ratio"], "Entry": r["entry"],
            "Stop_Loss": r["stop_loss"], "Target": r["target"],
            "Risk_Pct": r["risk_pct"], "Score": r["score"], "Reason": r["note"],
        } for r in all_rows])
        st.download_button(
            "Download CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="swift_trade_v5_scan.csv",
            mime="text/csv",
        )
        watchlist = "\n".join(f"NSE:{r['symbol']}" for r in picks)
        st.download_button(
            "Download TradingView Watchlist",
            watchlist,
            file_name="swift_trade_v5_watchlist.txt",
            mime="text/plain",
        )

    if result["skipped"]:
        with st.expander(f"Skipped symbols ({len(result['skipped'])})"):
            st.dataframe(pd.DataFrame(result["skipped"], columns=["Symbol", "Reason"]),
                         use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption("V5 is a research scanner, not an execution system. Validate every signal on the live exchange chart and paper-trade before risking capital.")


if __name__ == "__main__":
    main()
    
