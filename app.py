"""
Swift Trade v4 | Multi-Timeframe Breakout Scanner (NSE)

Logic in one line:
  1H = trend direction | 15M = breakout + volume (main setup) | 5M = confirmation

TWO different prices are used (this is the main fix over v3):
  SIGNAL price = close of the last COMPLETED 15M candle  -> keeps signals stable (no flicker)
  LIVE price   = newest 1-minute bar (running candle)     -> used for LTP, Entry, Change %, distance

DATA SOURCE: all price downloading lives in ONE section below ("DATA SOURCE LAYER").
When you get the broker API (5paisa / Groww), only that section changes.

Requirements (requirements.txt):
  streamlit
  yfinance
  pandas
  numpy
  streamlit-autorefresh   (needed for Auto Refresh to work)

NOTE: This file is saved in TWO parts. Part 1 first, then Part 2 pasted right below it.
"""

import time

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ==================== SETTINGS (change here if needed) ====================
IST = "Asia/Kolkata"
DATA_SOURCE = "yahoo"  # later: "broker" (after you connect 5paisa / Groww API)

TOP_N = 6              # how many stocks to show
RES_LOOKBACK = 20      # resistance = highest High of last 20 completed daily candles
VOL_MULT = 1.5         # breakout volume must be >= 1.5x normal (same time of day)
MAX_EXT = 2.0          # more than 2% above resistance = "late / overbought"
RSI_MAX = 70           # 15M RSI above this = overbought
NEAR_PCT = 1.0         # within 1% below resistance = "near breakout"
GAP_PCT = 0.3          # day opened more than 0.3% above resistance = gap-up
SL_PCT = 1.5           # stop loss = 1.5% below resistance ...
ATR_BUF = 0.5          # ... minus half of the 15M ATR (extra breathing room)
RR = 2.0               # target = Entry + 2 x risk
FRESH_BARS = 6         # breakout is "fresh" if within last 6 x 15M candles (1.5 hours)
STALE_MIN = 5          # live price older than this many minutes (market hours) = no BUY signal
MAX_JUMP_PCT = 8.0     # live price differing more than 8% from the signal price = bad tick, ignore it
TICK = 0.05            # NSE price tick (Entry / SL / Target are rounded to this)

SESSION_CLOSE = pd.Timedelta(hours=15, minutes=30)

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Swift Trade | Smart Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

for _k, _v in {
    "auto_refresh": False,
    "refresh_interval": 120,
    "last_scan_ts": 0.0,
    "last_scan_label": "",
    "last_price_label": "",
    "n_stale": 0,
    "scanned_once": False,
    "prev_buy": set(),
    "picks": [],
    "all_rows": [],
    "skipped": [],
    "n_scanned": 0,
    "n_avoid": 0,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ==================== CSS ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: linear-gradient(160deg, #0a0f1a 0%, #0d1b2a 40%, #0a1628 100%); color: #e0e6ed; }
.block-container { max-width: 1400px; padding: 1rem 1.5rem 2rem 1.5rem; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

.logo-area { display: flex; align-items: center; gap: 12px; }
.logo-icon { background: linear-gradient(135deg, #00e676, #00c853); width: 42px; height: 42px;
  border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.logo-text h1 { margin: 0; font-size: 1.6rem; font-weight: 800;
  background: linear-gradient(90deg, #00e676, #00bcd4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.logo-text p { margin: 0; font-size: 0.75rem; color: #7a8ba3; }

.index-card { background: linear-gradient(145deg, #0f2137, #0c1a2b); border: 1px solid #1a3a5c;
  border-radius: 12px; padding: 14px 16px; height: 100%; }
.index-name { font-size: 0.72rem; color: #7a8ba3; font-weight: 600; margin-bottom: 4px; }
.index-value { font-size: 1.25rem; font-weight: 700; color: #ffffff; }
.index-change-up { font-size: 0.8rem; color: #00e676; font-weight: 600; }
.index-change-down { font-size: 0.8rem; color: #ff5252; font-weight: 600; }

.section-label { font-size: 0.85rem; font-weight: 600; color: #8ba3c7; margin-bottom: 8px; margin-top: 4px; }

.banner { border-radius: 10px; padding: 10px 14px; font-size: 0.85rem; margin-bottom: 10px; }
.banner.warn { background: #2e220a; border: 1px solid #5c4a1a; color: #ffd180; }
.banner.info { background: #0d2b4e; border: 1px solid #1e4a7a; color: #9cc7f5; }

.summary-card { border-radius: 12px; padding: 14px 16px; height: 100%; }
.summary-card.blue { background: linear-gradient(135deg, #0d2b4e, #0a1f3a); border: 1px solid #1e4a7a; }
.summary-card.green { background: linear-gradient(135deg, #0a2e1a, #072416); border: 1px solid #1a5c30; }
.summary-card.orange { background: linear-gradient(135deg, #2e220a, #241a07); border: 1px solid #5c4a1a; }
.summary-card.red { background: linear-gradient(135deg, #2e0a0a, #240707); border: 1px solid #5c1a1a; }
.summary-title { font-size: 0.78rem; color: #8ba3c7; font-weight: 500; margin-bottom: 4px; }
.summary-value { font-size: 1.5rem; font-weight: 800; color: #ffffff; }
.summary-sub { font-size: 0.72rem; color: #7a8ba3; margin-top: 2px; }

.pick-card { background: linear-gradient(145deg, #0f2137, #0c1a2b); border: 2px solid #1a3a5c;
  border-radius: 14px; padding: 14px 16px; margin-bottom: 14px; }
.pick-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.pick-rank { color: #7a8ba3; font-weight: 700; font-size: 0.85rem; }
.pick-name { font-size: 1.25rem; font-weight: 800; color: #ffffff; margin-left: 4px; }
.pick-sector { font-size: 0.72rem; color: #7a8ba3; margin-top: 2px; }
.pick-ltp { text-align: right; font-size: 1.05rem; font-weight: 700; color: #ffffff; }
.pick-ltp .up { color: #00e676; font-size: 0.8rem; margin-left: 4px; }
.pick-ltp .down { color: #ff5252; font-size: 0.8rem; margin-left: 4px; }
.pick-ltp small { display: block; font-size: 0.66rem; color: #7a8ba3; font-weight: 500; margin-top: 2px; }
.pick-ltp.stale small { color: #ffb74d; }
.star { background: #ffd54f; color: #1a1200; font-size: 0.68rem; font-weight: 800;
  padding: 2px 8px; border-radius: 20px; margin-left: 8px; }
.status-pill { display: inline-block; margin: 10px 0 8px 0; padding: 4px 12px; border-radius: 20px;
  font-weight: 700; font-size: 0.82rem; background: #0a1628; }
.lamps { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.lamp { font-size: 0.74rem; font-weight: 600; padding: 3px 9px; border-radius: 6px; }
.lamp.on { background: #0a2e1a; color: #00e676; border: 1px solid #1a5c30; }
.lamp.off { background: #2e0a0a; color: #ff8a80; border: 1px solid #5c1a1a; }
.levels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 10px; }
.level { background: #0a1628; border-radius: 8px; padding: 6px 8px; }
.level .k { font-size: 0.66rem; color: #7a8ba3; }
.level .v { font-size: 0.95rem; font-weight: 700; color: #ffffff; }
.level.sl .v { color: #ff8a80; }
.level.tg .v { color: #69f0ae; }
.stats { display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.76rem; color: #8ba3c7; margin-bottom: 8px; }
.stats b { color: #e0e6ed; }
.advice { font-size: 0.8rem; color: #cfd8e3; border-top: 1px solid #12253a; padding-top: 8px; }

.stButton > button { border-radius: 8px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ==================== STOCK UNIVERSE ====================
SECTORS = {
    "Bank": ["KOTAKBANK", "ICICIBANK", "SBIN", "HDFCBANK", "AXISBANK", "INDUSINDBK", "BANDHANBNK", "FEDERALBNK"],
    "IT": ["TCS", "HCLTECH", "INFY", "WIPRO", "TECHM", "LTIM", "PERSISTENT", "COFORGE"],
    "Auto": ["M&M", "MARUTI", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO", "ASHOKLEY", "TVSMOTOR"],
    "Pharma": ["DRREDDY", "DIVISLAB", "SUNPHARMA", "CIPLA", "APOLLOHOSP", "LUPIN", "AUROPHARMA", "BIOCON"],
    "Energy": ["RELIANCE", "ONGC", "COALINDIA", "NTPC", "POWERGRID", "BPCL", "IOC", "ADANIGREEN"],
    "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP", "TATACONSUM"],
    "Metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC", "SAIL", "NATIONALUM", "JINDALSTEL"],
    "PSU": ["BEL", "HAL", "IRFC", "RVNL", "RECLTD", "PFC", "IRCTC", "NBCC"],
    "Defence": ["HAL", "BEL", "BHEL", "MAZDOCK", "COCHINSHIP", "BDL", "GRSE", "DATAPATTNS"],
    "Others": ["ASIANPAINT", "TITAN", "TRENT", "ADANIENT", "ETERNAL", "PAYTM", "POLYCAB", "DIXON", "LT", "ULTRACEMCO"],
}

INDEX_SYMBOLS = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN", "INDIA VIX": "^INDIAVIX"}

# ==================== STATUS DEFINITIONS ====================
STATUS = {
    "BUY":     {"label": "🟢 BUY NOW", "color": "#00e676", "prio": 0},
    "TRIGGER": {"label": "🟡 ট্রিগার আসছে", "color": "#ffd54f", "prio": 1},
    "NEAR":    {"label": "🟡 ব্রেকআউটের দোরগোড়ায়", "color": "#ffca28", "prio": 2},
    "LATE":    {"label": "🟠 দেরি / ওভারবট", "color": "#ff9800", "prio": 3},
    "WAIT":    {"label": "⚪ অপেক্ষা", "color": "#90a4ae", "prio": 4},
    "AVOID":   {"label": "🔴 এড়িয়ে চলুন", "color": "#ff5252", "prio": 5},
}

# ==================== TIME HELPERS ====================
def now_ist():
    return pd.Timestamp.now(tz=IST)


def to_ist_index(df):
    df = df.copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC").tz_convert(IST)
    else:
        idx = idx.tz_convert(IST)
    df.index = idx
    return df


def clean_daily(df):
    df = df.copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert(IST).tz_localize(None)
    df.index = idx.normalize()
    return df


def completed(df, minutes):
    """Keep only fully-closed candles (the running candle is dropped).
    The last candle of a day is cut at 15:30, so the final 1H candle (15:15-15:30)
    counts as complete right after the market closes."""
    if df is None or df.empty:
        return df
    idx = df.index
    end = pd.Series(idx + pd.Timedelta(minutes=minutes), index=idx)
    close = pd.Series(idx.normalize() + SESSION_CLOSE, index=idx)
    end = end.where(end <= close, close)
    return df[(end <= now_ist()).values]


def market_state():
    t = now_ist()
    mins = t.hour * 60 + t.minute
    if t.weekday() >= 5:
        return "closed", "আজ বাজার বন্ধ (শনি/রবি)। শেষ সেশনের ডেটা দেখানো হচ্ছে।"
    if mins < 9 * 60 + 15:
        return "closed", "বাজার এখনো খোলেনি। শেষ সেশনের ডেটা দেখানো হচ্ছে।"
    if mins > 15 * 60 + 30:
        return "closed", "বাজার বন্ধ। আজকের শেষ ডেটা দেখানো হচ্ছে।"
    if mins < 9 * 60 + 30:
        return "early", "৯:৩০ এর আগে সিগন্যাল ভরসাযোগ্য নয় (গ্যাপ ও এলোমেলো ওঠানামা)। ৯:৩০ এর পরে স্ক্যান করুন।"
    if 11 * 60 + 30 <= mins <= 13 * 60 + 30:
        return "slow", "এখন বাজার সাধারণত ঝিমিয়ে থাকে। নতুন এন্ট্রির সেরা সময় ৯:৪৫ থেকে ১০:৪৫।"
    return "open", ""


def tick(x, step=TICK):
    """Round a price to the NSE tick size."""
    return round(round(x / step) * step, 2)


# ==================== DATA SOURCE LAYER ====================
# Every function here returns: {SYMBOL: DataFrame[Open, High, Low, Close, Volume]}
# with a time index. SYMBOL is the plain NSE symbol (e.g. "RELIANCE", no ".NS").
# >>> When the broker API is ready, ONLY the three `source_*` functions and
# >>> `source_index` need to be rewritten. The rest of the app does not change.
OHLCV = ["Open", "High", "Low", "Close", "Volume"]
INTRADAY_PERIOD = {"1m": "2d", "5m": "5d", "15m": "1mo"}



def yahoo_ticker(sym):
    return sym + ".NS"


def _clean_ohlcv(d):
    """Clean OHLCV data by removing invalid prices and negative volume rows."""
    d = d[OHLCV].apply(pd.to_numeric, errors="coerce")
    d = d.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    d["Volume"] = d["Volume"].fillna(0)
    d = d[d["Volume"] >= 0].copy()
    d = d[(d[["Open", "High", "Low", "Close"]] > 0).all(axis=1)].copy()
    px = d[["Open", "High", "Low", "Close"]]
    d["High"] = px.max(axis=1)
    d["Low"] = px.min(axis=1)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d
  


def _yahoo_download(symbols, period, interval):
    tickers = [yahoo_ticker(s) for s in symbols]
    try:
        # auto_adjust=False -> raw prices, same as the TradingView chart
        raw = yf.download(tickers, period=period, interval=interval, group_by="ticker",
                          auto_adjust=False, progress=False, threads=True)
    except Exception:
        return {}
    if raw is None or raw.empty:
        return {}
    out = {}
    for s, t in zip(symbols, tickers):
        try:
            d = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
            if not all(c in d.columns for c in OHLCV):
                continue
            d = _clean_ohlcv(d)
            if len(d):
                out[s] = d
        except Exception:
            continue
    return out


def source_daily(symbols):
    if DATA_SOURCE == "yahoo":
        return _yahoo_download(symbols, "6mo", "1d")
    raise NotImplementedError("Broker API daily data is not connected yet")


def source_hourly(symbols):
    if DATA_SOURCE == "yahoo":
        return _yahoo_download(symbols, "3mo", "1h")
    raise NotImplementedError("Broker API hourly data is not connected yet")


def source_intraday(symbols, interval):
    """interval = '1m' | '5m' | '15m'"""
    if DATA_SOURCE == "yahoo":
        return _yahoo_download(symbols, INTRADAY_PERIOD[interval], interval)
    raise NotImplementedError("Broker API intraday data is not connected yet")


def source_index():
    """Returns {NAME: {"price", "change", "pct"}}"""
    if DATA_SOURCE != "yahoo":
        raise NotImplementedError("Broker API index data is not connected yet")
    out = {}
    for name, sym in INDEX_SYMBOLS.items():
        try:
            df = yf.download(sym, period="5d", interval="1d", progress=False, auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) >= 2:
                price = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                out[name] = {"price": price, "change": price - prev,
                             "pct": (price / prev - 1) * 100 if prev else 0.0}
        except Exception:
            continue
    return out


# ---- Cache layer ----
# A failed / empty download RAISES an error inside the cached function, because Streamlit
# never caches an error. So a bad download is never stored and is retried on the next run.
# All fast data (1m + 5m + 15m) is downloaded together under the same minute-bucket,
# so price, volume and candles always come from the same moment.
@st.cache_data(ttl=1800, show_spinner=False)
def _cached_daily(symbols, day_key):
    out = source_daily(list(symbols))
    if not out:
        raise RuntimeError("empty daily data")
    return out


@st.cache_data(ttl=600, show_spinner=False)
def _cached_hourly(symbols, bucket):
    out = source_hourly(list(symbols))
    if not out:
        raise RuntimeError("empty hourly data")
    return out


@st.cache_data(ttl=120, show_spinner=False)
def _cached_intraday(symbols, bucket):
    syms = list(symbols)
    data = {
        "15m": source_intraday(syms, "15m"),
        "5m": source_intraday(syms, "5m"),
        "1m": source_intraday(syms, "1m"),
    }
    if not data["15m"]:
        raise RuntimeError("empty 15m data")
    return data


@st.cache_data(ttl=60, show_spinner=False)
def _cached_index(bucket):
    out = source_index()
    if not out:
        raise RuntimeError("empty index data")
    return out


def _try(fn, *args, default=None):
    """Run a cached fetch, retry once, return `default` if it still fails."""
    for _ in range(2):
        try:
            return fn(*args)
        except Exception:
            continue
    return default


def get_daily(symbols):
    return _try(_cached_daily, tuple(symbols), str(now_ist().date()), default={})


def get_hourly(symbols):
    return _try(_cached_hourly, tuple(symbols), int(time.time() // 300), default={})


def get_intraday(symbols):
    return _try(_cached_intraday, tuple(symbols), int(time.time() // 60),
                default={"15m": {}, "5m": {}, "1m": {}})


def get_index():
    return _try(_cached_index, int(time.time() // 60), default={})


def clear_fast_cache():
    _cached_daily.clear()
    _cached_hourly.clear()
    _cached_intraday.clear()
    _cached_index.clear()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss.ne(0), 100)
    rsi = rsi.where(avg_gain.ne(0), 0)
    rsi = rsi.mask(avg_gain.eq(0) & avg_loss.eq(0), 50)
    return rsi.fillna(50)
    



def calculate_atr(df, period=14):
    if period <= 0:
        raise ValueError("ATR period must be greater than zero")

    prev_close = df["Close"].shift(1)

    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    atr = pd.Series(float("nan"), index=df.index, dtype="float64")

    if len(tr) < period:
        return atr

    initial_atr = tr.iloc[:period].mean()

    if pd.isna(initial_atr):
        return atr

    atr.iloc[period - 1] = initial_atr

    for i in range(period, len(tr)):
        current_tr = tr.iloc[i]

        if pd.isna(current_tr):
            atr.iloc[i] = atr.iloc[i - 1]
        else:
            atr.iloc[i] = (
                atr.iloc[i - 1] * (period - 1) + current_tr
            ) / period

    return atr



def nz(x, default=0.0):
    try:
        x = float(x)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def slot_volume_ratio(c15, session_date, ts):
    """Volume of one 15M candle vs the average of the same time-slot on previous days."""
    prior = c15[(c15["_date"] < session_date) & (c15["_tod"] == ts.time())]
    if prior.empty:
        return np.nan
    avg = float(prior["Volume"].tail(10).mean())
    cur = float(c15.loc[ts, "Volume"])
    return cur / avg if avg > 0 else np.nan


def day_volume_ratio(c15, session_date, last_tod):
    """Today's total volume so far vs the average volume of previous days up to the same time."""
    cum_today = float(c15[c15["_date"] == session_date]["Volume"].sum())
    prior = c15[(c15["_date"] < session_date) & (c15["_tod"] <= last_tod)]
    if prior.empty:
        return np.nan
    avg = float(prior.groupby("_date")["Volume"].sum().tail(10).mean())
    return cum_today / avg if avg > 0 else np.nan



def live_price(d_1m, d_5m, d_15, session_date):
    """Select the newest valid price across 1M, 5M and 15M data."""
    candidates = []

    for df, mins in ((d_1m, 1), (d_5m, 5), (d_15, 15)):
        if df is None or df.empty:
            continue

        x = to_ist_index(df).sort_index()
        x = x[x.index.date == session_date]

        if x.empty:
            continue

        ts = x.index[-1]
        price = nz(x["Close"].iloc[-1], 0.0)

        if price > 0:
            candidates.append((ts, price, mins))

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda item: (item[0], -item[2]), reverse=True)

    ts, price, mins = candidates[0]

    return price, ts, mins



# ===== END OF PART 1 — paste PART 2 right below this line =====

# ==================== CORE ANALYSIS ====================
def analyze(sym, sector, d_daily, d_1h, d_15, d_5, d_1m):
    """Returns (result_dict, None) or (None, reason_for_skipping)."""
    if any(df is None or df.empty for df in (d_daily, d_1h, d_15)):
        return None, "ডেটা পাওয়া যায়নি (টিকার বদলে গেছে কিনা দেখুন)"

    # ---- 15M candles: signal price = last COMPLETED candle ----
    raw15 = to_ist_index(d_15)
    session_date = raw15.index[-1].date()
    c15 = completed(raw15, 15)
    if c15 is None or len(c15) < 40:
        return None, "১৫ মিনিটের ডেটা কম"
    c15 = c15.copy()
    c15["_date"] = c15.index.date
    c15["_tod"] = c15.index.time
    today = c15[c15["_date"] == session_date]
    if today.empty:
        return None, "আজকের প্রথম ১৫ মিনিটের ক্যান্ডেল এখনো শেষ হয়নি (৯:৩০ এর পরে স্ক্যান করুন)"
    sig_price = float(today["Close"].iloc[-1])
    candle_end = today.index[-1] + pd.Timedelta(minutes=15)

    # ---- LIVE price (running candle included) ----
    lp, lp_ts, lp_min = live_price(d_1m, d_5, d_15, session_date)
    live_ok = lp is not None and abs(lp / sig_price - 1) * 100 <= MAX_JUMP_PCT
    if live_ok:
        price = lp
        price_ts = lp_ts
        price_end = lp_ts + pd.Timedelta(minutes=lp_min)
        src = {1: "লাইভ", 5: "লাইভ (5M)", 15: "১৫M"}.get(lp_min, "লাইভ")
        price_label = f"{src} · {lp_ts.strftime('%H:%M')}"
        limit = STALE_MIN
    else:
        price = sig_price
        price_ts = candle_end
        price_end = candle_end
        price_label = f"১৫M বন্ধ দাম · {candle_end.strftime('%H:%M')}"
        limit = STALE_MIN + 15   # a closed 15M candle is normally up to 15 min old
    lag_min = max(0.0, (now_ist() - price_end).total_seconds() / 60)
    stale = market_state()[0] != "closed" and lag_min > limit

    # ---- Daily resistance (completed days before the session, raw prices) ----
    daily = clean_daily(d_daily)
    comp = daily[daily.index < pd.Timestamp(session_date)]
    if len(comp) < RES_LOOKBACK + 1:
        return None, "দৈনিক ডেটা কম"
    resistance = float(comp["High"].tail(RES_LOOKBACK).max())
    prev_close = float(comp["Close"].iloc[-1])

    # ---- 1H trend (completed 1H candles only, compared with the stable signal price) ----
    h = completed(to_ist_index(d_1h), 60)["Close"].astype(float)
    if len(h) < 60:
        return None, "১ ঘণ্টার ডেটা কম"
    ema20 = float(h.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(h.ewm(span=50, adjust=False).mean().iloc[-1])
    trend_up = sig_price > ema20 and ema20 > ema50
    trend_down = sig_price < ema20 and ema20 < ema50

    # ---- 5M confirmation ----
    above_ema9 = False
    conf5 = False
    
    if d_5 is not None and not d_5.empty:
                     cc5 = completed(to_ist_index(d_5), 5)
                     if cc5 is not None:
                                 cc5 = cc5[cc5.index.date == session_date]

                                 if len(cc5) >= 10:
                                           ema9_5 = cc5["Close"].ewm(span=9, adjust=False).mean()
                                           above_ema9 = float(cc5["Close"].iloc[-1]) > float(ema9_5.iloc[-1])
                                           last3 = cc5.tail(3)
                                           conf5 = bool((last3["Close"] > resistance).all() and above_ema9)


    # ---- 15M breakout detection ----
    above = (today["Close"] > resistance).tolist()
    n_today = len(above)
    broke_today = any(above)
    # breakout = last completed 15M candle closed above resistance AND the LIVE price is still above it
    breakout = bool(above[-1]) and price > resistance
    gap = float(today["Open"].iloc[0]) > resistance * (1 + GAP_PCT / 100)

    # start of the CURRENT run above resistance (handles break -> fall -> re-break correctly)
    break_time = ""
    rvol_break = np.nan
    bars_since = 999
    if above[-1]:
        i = n_today - 1
        while i >= 0 and above[i]:
            i -= 1
        streak_start = i + 1
        ts = today.index[streak_start]
        break_time = ts.strftime("%H:%M")
        rvol_break = slot_volume_ratio(c15, session_date, ts)
        bars_since = n_today - 1 - streak_start
    fresh = bars_since <= FRESH_BARS

    drv = day_volume_ratio(c15, session_date, today.index[-1].time())
    
    vol_ratio = nz(rvol_break if breakout else drv, 0.0)

    vol_ok = vol_ratio >= VOL_MULT

    rsi15 = nz(calculate_rsi(c15["Close"]).iloc[-1], 50.0)
    atr15 = nz(calculate_atr(c15).iloc[-1], price * 0.003)

    ext = (price / resistance - 1) * 100
    change_pct = (price / prev_close - 1) * 100

    # ---- Status ----
    if trend_down:
        key, note = "AVOID", "১ ঘণ্টার ট্রেন্ড নিচের দিকে। এই স্টকে কিনবেন না।"
    elif breakout:
        if ext > MAX_EXT or rsi15 > RSI_MAX:
            key, note = "LATE", "অনেক উপরে উঠে গেছে। ধাওয়া করবেন না, পুলব্যাকের অপেক্ষা করুন।"
        elif not fresh:
            key, note = "LATE", f"ব্রেকআউট {break_time} এ হয়েছে, এখন আর ফ্রেশ নয়। পুলব্যাকের অপেক্ষা করুন।"
        elif not vol_ok:
            key, note = "WAIT", "ব্রেকআউট হয়েছে কিন্তু ভলিউম কম। দুর্বল ব্রেকআউট, ঝুঁকি বেশি।"
        elif not trend_up:
            key, note = "WAIT", "১ ঘণ্টার ট্রেন্ড এখনো পরিষ্কার নয়। অপেক্ষা করুন।"
        elif gap:
            key, note = "TRIGGER", "গ্যাপ-আপে ব্রেকআউট। প্রথম পুলব্যাক ধরে রাখলে তবেই ঢুকুন।"
        elif conf5:
            key, note = "BUY", "১H, ১৫M, ৫M তিনটিই মিলেছে। স্টপলস মেনে এন্ট্রি নিতে পারেন।"
        else:
            key, note = "TRIGGER", "ভলিউমসহ ব্রেকআউট হয়েছে। ৫ মিনিটের নিশ্চিতকরণের জন্য আরেকটু অপেক্ষা করুন।"
    elif broke_today:
        key, note = "WAIT", "রেজিস্ট্যান্সের উপরে উঠে আবার নিচে নেমেছে (ফেক ব্রেকআউট)। এড়িয়ে চলুন।"
    elif trend_up and ext >= -NEAR_PCT:
        key, note = "NEAR", "রেজিস্ট্যান্সের খুব কাছে। ভলিউমসহ ১৫ মিনিটে ক্লোজ হলে তবেই ঢুকুন।"
    else:
        key, note = "WAIT", "এখনো রেজিস্ট্যান্স থেকে দূরে বা সেটআপ তৈরি হয়নি।"

    # ---- Market closed safety ----
    if market_state()[0] == "closed":
        key = "WAIT"
        note = "বাজার বন্ধ। পরবর্তী ট্রেডিং সেশনে নতুন স্ক্যান করুন।"

    # Never give an entry signal on an old price
    if stale and key in ("BUY", "TRIGGER", "NEAR"):
        key = "WAIT"
        note = (f"দাম প্রায় {lag_min:.0f} মিনিট পুরোনো। চার্টে লাইভ দাম মিলিয়ে নিন, "
                "তারপর সিদ্ধান্ত নিন।")

    # ---- Entry / Stop loss / Target (rounded to NSE tick) ----
    entry = price if breakout else resistance * 1.001
    sl = resistance * (1 - SL_PCT / 100) - ATR_BUF * atr15
    if sl >= entry:
        sl = entry * (1 - SL_PCT / 100)
    target = entry + RR * (entry - sl)
    risk_pct = (entry - sl) / entry * 100 if entry > 0 else 0.0

    l1h = bool(trend_up)
    l15 = bool(breakout and vol_ok)
    l5 = bool(conf5 if breakout else above_ema9)

    # ---- Ranking score (higher = better, inside the same status) ----
    score = (min(vol_ratio, 4.0) * 2
             + (1.0 if l5 else 0.0)
             + (1.0 if 55 <= rsi15 <= 70 else 0.0)
             + (1.0 if (breakout and fresh) else 0.0)
             - abs(ext) * 0.5)

    return {
        "Stock": sym,
        "Sector": sector,
        "Status": STATUS[key]["label"],
        "LTP": round(price, 2),
        "Price Time": price_label,
        "Change %": round(change_pct, 2),
        "Resistance": round(resistance, 2),
        "Dist from Res %": round(ext, 2),
        "Entry": tick(entry),
        "Stop Loss": tick(sl),
        "Target": tick(target),
        "Risk %": round(risk_pct, 2),
        "Volume x": round(vol_ratio, 2),
        "RSI 15M": round(rsi15, 1),
        "Breakout Time": break_time,
        "Note": note,
        "_key": key,
        "_prio": STATUS[key]["prio"],
        "_score": score,
        "_l1h": l1h,
        "_l15": l15,
        "_l5": l5,
        "_price_ts": price_ts,
        "_lag": lag_min,
        "_stale": bool(stale),
    }, None


def run_scan(active_sectors, force=False):
    sym_sector = {}
    for sec in active_sectors:
        for s in SECTORS[sec]:
            if s not in sym_sector:
                sym_sector[s] = sec
    symbols = list(sym_sector.keys())

    # Manual click = always pull fresh data (skip the cache)
    if force:
        clear_fast_cache()

    bar = st.progress(0, text="দৈনিক ডেটা আনা হচ্ছে...")
    daily = get_daily(symbols)
    bar.progress(30, text="১ ঘণ্টার ডেটা আনা হচ্ছে...")
    h1 = get_hourly(symbols)
    bar.progress(55, text="১৫ / ৫ / ১ মিনিটের ডেটা আনা হচ্ছে...")
    intra = get_intraday(symbols)
    m15, m5, m1 = intra.get("15m", {}), intra.get("5m", {}), intra.get("1m", {})
    bar.progress(85, text="বিশ্লেষণ চলছে...")

    if not daily or not h1 or not m15:
        bar.empty()
        return [], [("ডেটা সোর্স", "ডেটা আসেনি। ইন্টারনেট / ডেটা সোর্স দেখুন, তারপর আবার স্ক্যান করুন।")]

    rows, skipped = [], []
    for sym in symbols:
        try:
            r, why = analyze(sym, sym_sector[sym], daily.get(sym), h1.get(sym),
                             m15.get(sym), m5.get(sym), m1.get(sym))
            if r:
                rows.append(r)
            else:
                skipped.append((sym, why))
        except Exception as e:
            skipped.append((sym, str(e)))

    bar.progress(100, text="স্ক্যান সম্পন্ন!")
    time.sleep(0.3)
    bar.empty()
    return rows, skipped


def tv_symbol(sym):
    """TradingView ticker format (hyphen / & become underscore)."""
    return "NSE:" + sym.replace("-", "_").replace("&", "_")


# ==================== MAIN UI ====================
def main():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        <div class="logo-area">
          <div class="logo-icon">📈</div>
          <div class="logo-text">
            <h1>Swift Trade</h1>
            <p>Smart Stock Scanner | Multi-Timeframe Breakout & Trend Filter</p>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.write("")
        if HAS_AUTOREFRESH:
            ar_on = st.toggle("🔄 অটো রিফ্রেশ (২ মি)", value=st.session_state["auto_refresh"])
            if ar_on != st.session_state["auto_refresh"]:
                st.session_state["auto_refresh"] = ar_on
                st.rerun()
            if st.session_state["auto_refresh"]:
                st_autorefresh(interval=st.session_state["refresh_interval"] * 1000, key="datarefresh")
        else:
            st.caption("অটো রিফ্রেশের জন্য requirements.txt-এ streamlit-autorefresh যোগ করুন")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Index bar
    idx_data = get_index()
    if idx_data:
        cols = st.columns(len(idx_data))
        for i, (k, v) in enumerate(idx_data.items()):
            with cols[i]:
                ch_class = "index-change-up" if v["change"] >= 0 else "index-change-down"
                sign = "+" if v["change"] >= 0 else ""
                st.markdown(f"""
                <div class="index-card">
                  <div class="index-name">{k}</div>
                  <div class="index-value">{v['price']:,.2f}</div>
                  <div class="{ch_class}">{sign}{v['change']:,.2f} ({sign}{v['pct']:.2f}%)</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    # Sector filter
    all_secs = list(SECTORS.keys())
    selected_sectors = all_secs
    with st.expander("⚙ সেক্টর ও সেটিংস ফিল্টার (ক্লিক করে খুলুন)", expanded=False):
        chosen = st.multiselect("সেক্টর নির্বাচন করুন:", all_secs, default=all_secs)
        if chosen:
            selected_sectors = chosen


    m_status, m_msg = market_state()
    if m_msg:
        b_type = "warn" if m_status != "open" else "info"
        st.markdown(f'<div class="banner {b_type}">📢 <b>বাজার পরিস্থিতি:</b> {m_msg}</div>', unsafe_allow_html=True)

    c_scan, c_clear, c_info = st.columns([1.2, 1, 3])
    with c_scan:
        scan_clicked = st.button("🚀 স্ক্যান শুরু করুন", type="primary", use_container_width=True)
    with c_clear:
        clear_clicked = st.button("🗑 রিসেট", use_container_width=True)

    if clear_clicked:
        st.session_state["picks"] = []
        st.session_state["all_rows"] = []
        st.session_state["skipped"] = []
        st.session_state["n_scanned"] = 0
        st.session_state["n_avoid"] = 0
        st.session_state["n_stale"] = 0
        st.session_state["prev_buy"] = set()
        st.session_state["scanned_once"] = True   # stay blank until the next scan click
        st.rerun()

    # ---- When to scan: first load, manual click, or auto-refresh due (market hours only) ----
    auto_due = (
        HAS_AUTOREFRESH
        and st.session_state["auto_refresh"]
        and m_status != "closed"
        and (time.time() - st.session_state["last_scan_ts"]) >= (st.session_state["refresh_interval"] - 5)
    )
    if scan_clicked or auto_due or not st.session_state["scanned_once"]:
        rows, skipped = run_scan(selected_sectors, force=scan_clicked)

        valid = [r for r in rows if r["_key"] != "AVOID"]
        valid.sort(key=lambda x: (x["_prio"], -x["_score"]))
        picks = valid[:TOP_N]

        # Alert when a stock newly turns BUY since the previous scan
        buy_now = {r["Stock"] for r in rows if r["_key"] == "BUY"}
        new_buy = buy_now - st.session_state["prev_buy"]
        if new_buy and st.session_state["scanned_once"]:
            st.toast("🟢 নতুন BUY সিগন্যাল: " + ", ".join(sorted(new_buy)), icon="🔔")
        st.session_state["prev_buy"] = buy_now

        # Newest price time + how many stocks have an old price
        stamps = [r["_price_ts"] for r in rows if r.get("_price_ts") is not None]
        
        price_lbl = max(stamps).strftime("%H:%M") if stamps else "N/A"


        st.session_state["picks"] = picks
        st.session_state["all_rows"] = rows
        st.session_state["skipped"] = skipped
        st.session_state["n_scanned"] = len(rows)
        st.session_state["n_avoid"] = len([r for r in rows if r["_key"] == "AVOID"])
        st.session_state["n_stale"] = len([r for r in rows if r["_stale"]])
        st.session_state["last_scan_ts"] = time.time()
        st.session_state["last_scan_label"] = now_ist().strftime("%I:%M:%S %p")
        st.session_state["last_price_label"] = price_lbl
        st.session_state["scanned_once"] = True

    picks = st.session_state["picks"]
    all_rows = st.session_state["all_rows"]
    skipped = st.session_state["skipped"]

    # Old-price warning (only while market is open)
    n_stale = st.session_state["n_stale"]
    if all_rows and n_stale > 0 and m_status != "closed":
        st.markdown(
            f'<div class="banner warn">⏱ <b>সতর্কতা:</b> {n_stale} টি স্টকের দাম {STALE_MIN} মিনিটের বেশি পুরোনো। '
            f'ডেটা সোর্স দেরিতে আপডেট হচ্ছে। এই স্টকগুলোতে BUY / TRIGGER সিগন্যাল দেওয়া হচ্ছে না, '
            f'এন্ট্রির আগে চার্টে লাইভ দাম মিলিয়ে নিন।</div>',
            unsafe_allow_html=True,
        )

    if all_rows:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.markdown(f'<div class="summary-card blue"><div class="summary-title">স্ক্যান করা স্টক</div><div class="summary-value">{st.session_state["n_scanned"]}</div><div class="summary-sub">নির্বাচিত সেক্টর থেকে</div></div>', unsafe_allow_html=True)
        with s2:
            st.markdown(f'<div class="summary-card green"><div class="summary-title">আজকের সেরা সুযোগ</div><div class="summary-value">{len(picks)}</div><div class="summary-sub">শীর্ষ রেংকড স্টক</div></div>', unsafe_allow_html=True)
        with s3:
            st.markdown(f'<div class="summary-card orange"><div class="summary-title">নেগেটিভ ট্রেন্ড (এড়িয়ে চলুন)</div><div class="summary-value">{st.session_state["n_avoid"]}</div><div class="summary-sub">নিচের দিকে ঝুঁকিপূর্ণ</div></div>', unsafe_allow_html=True)
        with s4:
            lbl = st.session_state["last_scan_label"] if st.session_state["last_scan_label"] else "এখনই"
            if st.session_state["auto_refresh"] and HAS_AUTOREFRESH:
                sub = "স্বয়ংক্রিয় আপডেট চালু"
            else:
                sub = "ম্যানুয়াল স্ক্যান"
            if st.session_state["last_price_label"]:
                sub += f" | দাম: {st.session_state['last_price_label']}"
            st.markdown(f'<div class="summary-card blue"><div class="summary-title">সর্বশেষ স্ক্যান</div><div class="summary-value" style="font-size:1.1rem; margin-top:4px;">{lbl}</div><div class="summary-sub">{sub}</div></div>', unsafe_allow_html=True)

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        st.markdown(f"### 🏆 আজকের সেরা {len(picks)} টি স্টক (ব্রেকআউট ও ট্রেন্ড ফিল্টার অনুযায়ী)", unsafe_allow_html=True)
        st.markdown("<div class='section-label'>প্রতিটি কার্ডে এন্ট্রি, স্টপলস এবং টার্গেট দেওয়া আছে:</div>", unsafe_allow_html=True)

        # Export buttons (TradingView watchlist + CSV)
        if picks:
            e1, e2, e3 = st.columns([1.3, 1.3, 3])
            with e1:
                st.download_button(
                    "📥 TradingView Watchlist",
                    data="\n".join(tv_symbol(p["Stock"]) for p in picks),
                    file_name="swift_trade_watchlist.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with e2:
                df_exp = pd.DataFrame(all_rows)
                df_exp = df_exp[[c for c in df_exp.columns if not c.startswith("_")]]
                st.download_button(
                    "📥 সব ফলাফল CSV",
                    data=df_exp.to_csv(index=False).encode("utf-8-sig"),
                    file_name="swift_trade_scan.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        actionable = [p for p in picks if p["_key"] in ("BUY", "TRIGGER", "NEAR")]
        if not actionable:
            st.info("এই মুহূর্তে কোনো স্টক BUY / TRIGGER / NEAR জোনে নেই। নিচের কার্ডগুলো শুধু নজরে রাখার জন্য, এন্ট্রির জন্য নয়।")

        if picks:
            cols = st.columns(2)
            for i, p in enumerate(picks):
                col = cols[i % 2]
                with col:
                    ch_str = f"+{p['Change %']}%" if p['Change %'] >= 0 else f"{p['Change %']}%"
                    ch_col = "up" if p['Change %'] >= 0 else "down"
                    l1h = "on" if p["_l1h"] else "off"
                    l15 = "on" if p["_l15"] else "off"
                    l5 = "on" if p["_l5"] else "off"
                    ltp_cls = "pick-ltp stale" if p["_stale"] else "pick-ltp"
                    star_html = '<span class="star">★ BUY সিগন্যাল</span>' if p["_key"] == "BUY" else ""
                    brk_html = f'<div>ব্রেকআউট: <b>{p["Breakout Time"]}</b></div>' if p["Breakout Time"] else ""

                    st.markdown(f"""
                    <div class="pick-card">
                      <div class="pick-top">
                        <div>
                          <span class="pick-rank">#{i+1}</span>
                          <span class="pick-name">{p['Stock']}</span>{star_html}
                          <div class="pick-sector">সেক্টর: {p['Sector']}</div>
                        </div>
                        <div class="{ltp_cls}">
                          ₹{p['LTP']:,.2f}
                          <span class="{ch_col}">({ch_str})</span>
                          <small>{p['Price Time']}</small>
                        </div>
                      </div>

                      <div><span class="status-pill" style="color: {STATUS[p['_key']]['color']}; border: 1px solid {STATUS[p['_key']]['color']};">{p['Status']}</span></div>

                      <div class="lamps">
                        <span class="lamp {l1h}">1H ট্রেন্ড {('✅' if p["_l1h"] else '❌')}</span>
                        <span class="lamp {l15}">15M ব্রেকআউট+ভলিউম {('✅' if p["_l15"] else '❌')}</span>
                        <span class="lamp {l5}">5M কনফার্মেশন {('✅' if p["_l5"] else '❌')}</span>
                      </div>

                      <div class="levels">
                   
                        <div class="level"><div class="k">এন্ট্রি (Entry)</div><div class="v">₹{p['Entry']:,.2f}</div></div>

                        <div class="level sl"><div class="k">স্টপলস (SL)</div><div class="v">₹{p['Stop Loss']:,.2f}</div></div>
                        <div class="level tg"><div class="k">টার্গেট (Target)</div><div class="v">₹{p['Target']:,.2f}</div></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()


