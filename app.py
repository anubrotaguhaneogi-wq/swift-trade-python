"""
Swift Trade v2 | Multi-Timeframe Breakout Scanner (NSE)

Logic in one line:
  1H = trend direction | 15M = breakout + volume (main setup) | 5M = confirmation
Output: best 6 stocks across all sectors, each with Entry / Stop Loss / Target.

Requirements (requirements.txt):
  streamlit
  yfinance
  pandas
  numpy
  streamlit-autorefresh   (optional - makes Auto Refresh work smoothly)
"""

import html
import time

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except Exception:
    HAS_AUTOREFRESH = False

# ==================== SETTINGS (change here if needed) ====================
IST = "Asia/Kolkata"
TOP_N = 6              # how many stocks to show
RES_LOOKBACK = 20      # resistance = highest High of last 20 completed daily candles
VOL_MULT = 1.5         # breakout volume must be >= 1.5x normal (same time of day)
MAX_EXT = 2.0          # more than 2% above resistance = "late / overbought"
RSI_MAX = 75           # 15M RSI above this = overbought
NEAR_PCT = 1.0         # within 1% below resistance = "near breakout"
GAP_PCT = 0.3          # day opened more than 0.3% above resistance = gap-up
SL_PCT = 1.5           # stop loss = 1.5% below resistance ...
ATR_BUF = 0.5          # ... minus half of the 15M ATR (extra breathing room)
RR = 2.0               # target = Entry + 2 x risk

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
    """Drop the candle that is still forming right now."""
    if df is None or df.empty:
        return df
    cutoff = now_ist() + pd.Timedelta(seconds=20)
    return df[(df.index + pd.Timedelta(minutes=minutes)) <= cutoff]


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


# ==================== DATA ====================
@st.cache_data(ttl=45, show_spinner=False)
def get_index_snapshot():
    out = {}
    for name, sym in INDEX_SYMBOLS.items():
        try:
            df = yf.download(sym, period="5d", interval="1d", progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) >= 2:
                price = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                out[name] = {"price": price, "change": price - prev, "pct": (price / prev - 1) * 100 if prev else 0.0}
        except Exception:
            continue
    return out


@st.cache_data(ttl=60, show_spinner=False)
def fetch_batch(tickers, period, interval):
    """One download call for many stocks. Returns {ticker: OHLCV dataframe}."""
    out = {}
    cols = ["Open", "High", "Low", "Close", "Volume"]
    try:
        raw = yf.download(list(tickers), period=period, interval=interval, group_by="ticker",
                          auto_adjust=True, progress=False, threads=True)
    except Exception:
        return out
    if raw is None or raw.empty:
        return out
    for t in tickers:
        try:
            d = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
            if not all(c in d.columns for c in cols):
                continue
            d = d[cols].dropna()
            if len(d):
                out[t] = d
        except Exception:
            continue
    return out


# ==================== INDICATORS ====================
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
    return rsi.fillna(50)


def calculate_atr(df, period=14):
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def nz(x, default=0.0):
    try:
        x = float(x)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def slot_volume_ratio(c15, session_date, ts):
    """Volume of one 15M candle vs the average of the same time slot on previous days."""
    prior = c15[(c15["_date"] < session_date) & (c15["_tod"] == ts.time())]
    if prior.empty:
        return np.nan
    avg = float(prior["Volume"].tail(10).mean())
    cur = float(c15.loc[ts, "Volume"])
    return cur / avg if avg > 0 else np.nan


def day_volume_ratio(c15, session_date, last_tod):
    """Today's total volume so far vs average of previous days up to the same time."""
    cum_today = float(c15[c15["_date"] == session_date]["Volume"].sum())
    prior = c15[(c15["_date"] < session_date) & (c15["_tod"] <= last_tod)]
    if prior.empty:
        return np.nan
    avg = float(prior.groupby("_date")["Volume"].sum().tail(10).mean())
    return cum_today / avg if avg > 0 else np.nan


# ==================== CORE ANALYSIS ====================
def analyze(sym, sector, d_daily, d_1h, d_15, d_5):
    """Returns (result_dict, None) or (None, reason_for_skipping)."""
    if d_daily is None or d_1h is None or d_15 is None or d_5 is None:
        return None, "ডেটা পাওয়া যায়নি (টিকার বদলে গেছে কিনা দেখুন)"

    # ---- 15M candles (completed only) ----
    c15 = completed(to_ist_index(d_15), 15)
    if c15 is None or len(c15) < 40:
        return None, "১৫ মিনিটের ডেটা কম"
    c15 = c15.copy()
    c15["_date"] = c15.index.date
    c15["_tod"] = c15.index.time
    session_date = c15["_date"].iloc[-1]
    today = c15[c15["_date"] == session_date]
    if today.empty:
        return None, "আজকের ১৫ মিনিটের ডেটা নেই"

    # ---- Daily resistance (completed days before the session) ----
    daily = clean_daily(d_daily)
    comp = daily[daily.index < pd.Timestamp(session_date)]
    if len(comp) < RES_LOOKBACK + 1:
        return None, "দৈনিক ডেটা কম"
    resistance = float(comp["High"].tail(RES_LOOKBACK).max())
    prev_close = float(comp["Close"].iloc[-1])
    if resistance <= 0 or prev_close <= 0:
        return None, "ডেটা ত্রুটি"

    # ---- 1H trend ----
    h = to_ist_index(d_1h)["Close"].astype(float)
    if len(h) < 60:
        return None, "১ ঘণ্টার ডেটা কম"
    ema20 = float(h.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(h.ewm(span=50, adjust=False).mean().iloc[-1])

    # ---- 5M confirmation ----
    f5 = to_ist_index(d_5)
    price = nz(f5["Close"].iloc[-1], 0.0)
    if price <= 0:
        price = nz(c15["Close"].iloc[-1], 0.0)
    if price <= 0:
        return None, "দাম পাওয়া যায়নি"
    cc5 = completed(f5, 5)
    above_ema9 = False
    conf5 = False
    if cc5 is not None and len(cc5) >= 10:
        ema9_5 = cc5["Close"].ewm(span=9, adjust=False).mean()
        above_ema9 = float(cc5["Close"].iloc[-1]) > float(ema9_5.iloc[-1])
        last3 = cc5.tail(3)
        conf5 = bool((last3["Close"] > resistance).all() and above_ema9)

    trend_up = price > ema20 and ema20 > ema50
    trend_down = price < ema20 and ema20 < ema50

    # ---- 15M breakout detection ----
    closes_above = today[today["Close"] > resistance]
    broke_today = not closes_above.empty
    holding = float(today["Close"].iloc[-1]) > resistance
    breakout = broke_today and holding
    gap = float(today["Open"].iloc[0]) > resistance * (1 + GAP_PCT / 100)

    break_time = ""
    rvol_break = np.nan
    if broke_today:
        ts = closes_above.index[0]
        break_time = ts.strftime("%H:%M")
        rvol_break = slot_volume_ratio(c15, session_date, ts)

    drv = day_volume_ratio(c15, session_date, today.index[-1].time())
    vol_ratio = nz(max(nz(rvol_break, 0.0), nz(drv, 0.0)) if breakout else nz(drv, 0.0), 0.0)
    vol_ok = vol_ratio >= VOL_MULT

    rsi15 = nz(calculate_rsi(c15["Close"]).iloc[-1], 50.0)
    atr15 = nz(calculate_atr(c15).iloc[-1], price * 0.003)

    ext = (price / resistance - 1) * 100
    change_pct = (price / prev_close - 1) * 100

    # ---- Status ----
    note = ""
    if trend_down:
        key, note = "AVOID", "১ ঘণ্টার ট্রেন্ড নিচের দিকে। এই স্টকে কিনবেন না।"
    elif breakout:
        if ext > MAX_EXT or rsi15 > RSI_MAX:
            key, note = "LATE", "অনেক উপরে উঠে গেছে। ধাওয়া করবেন না, পুলব্যাকের অপেক্ষা করুন।"
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
    elif broke_today and not holding:
        key, note = "WAIT", "রেজিস্ট্যান্সের উপরে উঠে আবার নিচে নেমেছে (ফেক ব্রেকআউট)। এড়িয়ে চলুন।"
    elif trend_up and ext >= -NEAR_PCT:
        key, note = "NEAR", "রেজিস্ট্যান্সের খুব কাছে। ভলিউমসহ ১৫ মিনিটে ক্লোজ হলে তবেই ঢুকুন।"
    else:
        key, note = "WAIT", "এখনো রেজিস্ট্যান্স থেকে দূরে বা সেটআপ তৈরি হয়নি।"

    # ---- Entry / Stop loss / Target ----
    entry = price if breakout else resistance * 1.001
    sl = resistance * (1 - SL_PCT / 100) - ATR_BUF * atr15
    if sl >= entry:
        sl = entry * (1 - SL_PCT / 100)
    target = entry + RR * (entry - sl)

    l1h = bool(trend_up)
    l15 = bool(breakout and vol_ok)
    l5 = bool(conf5 if breakout else above_ema9)

    # ---- Ranking score (higher = better, inside the same status) ----
    score = (min(vol_ratio, 4.0) * 2
             + (1.0 if l5 else 0.0)
             + (1.0 if 55 <= rsi15 <= 70 else 0.0)
             - abs(ext) * 0.5)

    return {
        "Stock": sym,
        "Sector": sector,
        "Status": STATUS[key]["label"],
        "LTP": round(price, 2),
        "Change %": round(change_pct, 2),
        "Resistance": round(resistance, 2),
        "Dist from Res %": round(ext, 2),
        "Entry": round(entry, 2),
        "Stop Loss": round(sl, 2),
        "Target": round(target, 2),
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
    }, None


def run_scan(active_sectors):
    sym_sector = {}
    for sec in active_sectors:
        for s in SECTORS[sec]:
            if s not in sym_sector:
                sym_sector[s] = sec
    symbols = list(sym_sector.keys())
    tickers = tuple(s + ".NS" for s in symbols)

    bar = st.progress(0, text="দৈনিক ডেটা আনা হচ্ছে...")
    daily = fetch_batch(tickers, "6mo", "1d")
    bar.progress(25, text="১ ঘণ্টার ডেটা আনা হচ্ছে...")
    h1 = fetch_batch(tickers, "3mo", "1h")
    bar.progress(50, text="১৫ মিনিটের ডেটা আনা হচ্ছে...")
    m15 = fetch_batch(tickers, "1mo", "15m")
    bar.progress(75, text="৫ মিনিটের ডেটা আনা হচ্ছে...")
    m5 = fetch_batch(tickers, "5d", "5m")
    bar.progress(90, text="বিশ্লেষণ চলছে...")

    rows, skipped = [], []
    for sym in symbols:
        t = sym + ".NS"
        try:
            r, why = analyze(sym, sym_sector[sym], daily.get(t), h1.get(t), m15.get(t), m5.get(t))
        except Exception as e:  # one bad stock must never stop the scan
            r, why = None, f"ত্রুটি: {type(e).__name__}"
        if r:
            rows.append(r)
        else:
            skipped.append(f"{sym}: {why}")
    bar.empty()

    ranked = sorted(rows, key=lambda x: (x["_prio"], -x["_score"]))
    candidates = [r for r in ranked if r["_key"] != "AVO
