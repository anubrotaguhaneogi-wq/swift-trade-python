import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="Swift Trade | Smart Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== AUTO REFRESH ====================
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 60
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# ==================== CUSTOM CSS ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: linear-gradient(160deg, #0a0f1a 0%, #0d1b2a 40%, #0a1628 100%);
    color: #e0e6ed;
}

.block-container {
    max-width: 1400px;
    padding: 1rem 1.5rem 2rem 1.5rem;
}

#MainMenu, footer, header {visibility: hidden;}
.stDeployButton {display: none;}

.logo-area {
    display: flex;
    align-items: center;
    gap: 12px;
}
.logo-icon {
    background: linear-gradient(135deg, #00e676, #00c853);
    width: 42px;
    height: 42px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
}
.logo-text h1 {
    margin: 0;
    font-size: 1.6rem;
    font-weight: 800;
    background: linear-gradient(90deg, #00e676, #00bcd4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.logo-text p {
    margin: 0;
    font-size: 0.75rem;
    color: #7a8ba3;
}

.index-card {
    background: linear-gradient(145deg, #0f2137, #0c1a2b);
    border: 1px solid #1a3a5c;
    border-radius: 12px;
    padding: 14px 16px;
    height: 100%;
}
.index-name {
    font-size: 0.72rem;
    color: #7a8ba3;
    font-weight: 600;
    margin-bottom: 4px;
}
.index-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: #ffffff;
}
.index-change-up {
    font-size: 0.8rem;
    color: #00e676;
    font-weight: 600;
}
.index-change-down {
    font-size: 0.8rem;
    color: #ff5252;
    font-weight: 600;
}

.section-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #8ba3c7;
    margin-bottom: 8px;
    margin-top: 4px;
}

.summary-card {
    border-radius: 12px;
    padding: 16px 18px;
    height: 100%;
}
.summary-card.blue {
    background: linear-gradient(135deg, #0d2b4e, #0a1f3a);
    border: 1px solid #1e4a7a;
}
.summary-card.green {
    background: linear-gradient(135deg, #0a2e1a, #072416);
    border: 1px solid #1a5c30;
}
.summary-card.orange {
    background: linear-gradient(135deg, #2e220a, #241a07);
    border: 1px solid #5c4a1a;
}
.summary-card.red {
    background: linear-gradient(135deg, #2e0a0a, #240707);
    border: 1px solid #5c1a1a;
}
.summary-title {
    font-size: 0.78rem;
    color: #8ba3c7;
    font-weight: 500;
    margin-bottom: 6px;
}
.summary-value {
    font-size: 1.6rem;
    font-weight: 800;
    color: #ffffff;
}
.summary-sub {
    font-size: 0.75rem;
    color: #7a8ba3;
    margin-top: 2px;
}

.bottom-card {
    background: linear-gradient(145deg, #0f2137, #0c1a2b);
    border: 1px solid #1a3a5c;
    border-radius: 12px;
    padding: 16px;
    height: 100%;
}
.bottom-card h4 {
    margin: 0 0 12px 0;
    font-size: 0.95rem;
    font-weight: 700;
    color: #e0e6ed;
}
.gainer-item, .loser-item, .watch-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid #12253a;
    font-size: 0.85rem;
}
.gainer-item:last-child, .loser-item:last-child, .watch-item:last-child {
    border-bottom: none;
}

.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: none !important;
}
</style>
""", unsafe_allow_html=True)

# ==================== DATA ====================
SECTORS = {
    "Bank": ["KOTAKBANK", "ICICIBANK", "SBIN", "HDFCBANK", "AXISBANK", "INDUSINDBK", "BANDHANBNK", "FEDERALBNK"],
    "IT": ["TCS", "HCLTECH", "INFY", "WIPRO", "TECHM", "LTIM", "PERSISTENT", "COFORGE"],
    "Auto": ["M&M", "MARUTI", "BAJAJ-AUTO", "EICHERMOT", "TATAMOTORS", "HEROMOTOCO", "ASHOKLEY", "TVSMOTOR"],
    "Pharma": ["DRREDDY", "DIVISLAB", "SUNPHARMA", "CIPLA", "APOLLOHOSP", "LUPIN", "AUROPHARMA", "BIOCON"],
    "Energy": ["RELIANCE", "ONGC", "COALINDIA", "NTPC", "POWERGRID", "BPCL", "IOC", "ADANIGREEN"],
    "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP", "TATACONSUM"],
    "Metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC", "SAIL", "NATIONALUM", "JINDALSTEL"],
    "PSU": ["BEL", "HAL", "IRFC", "RVNL", "RECLTD", "PFC", "IRCTC", "NBCC"],
    "Defence": ["HAL", "BEL", "BHEL", "MAZDOCK", "COCHINSHIP", "BDL", "GRSE", "DATAPATTNS"],
    "Others": ["ASIANPAINT", "TITAN", "TRENT", "ADANIENT", "ZOMATO", "PAYTM", "POLYCAB", "DIXON", "LT", "ULTRACEMCO"]
}

INDEX_SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "INDIA VIX": "^INDIAVIX"
}

@st.cache_data(ttl=45)
def get_index_data(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="5m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 2:
            df = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
        if len(df) < 2:
            return None
        price = float(df["Close"].iloc[-1])
        daily = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
        if isinstance(daily.columns, pd.MultiIndex):
            daily.columns = daily.columns.get_level_values(0)
        if len(daily) >= 2:
            prev = float(daily["Close"].iloc[-2])
        else:
            prev = float(df["Close"].iloc[-2])
        change = price - prev
        pct = (change / prev) * 100 if prev else 0
        return {"price": price, "change": change, "pct": pct}
    except:
        return None

@st.cache_data(ttl=60)
def get_stock_data(sym):
    """Fetch clean daily OHLCV data. Intraday prices never overwrite daily candles."""
    try:
        df = yf.download(
            sym + ".NS",
            period="1y",
            interval="1d",
            progress=False,
            auto_adjust=True
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        required = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in df.columns for col in required):
            return pd.DataFrame()
        return df[required].dropna()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=30)
def get_live_price(sym):
    """Get the latest intraday quote separately from daily historical candles."""
    try:
        intra = yf.download(
            sym + ".NS",
            period="1d",
            interval="5m",
            progress=False,
            auto_adjust=True
        )
        if isinstance(intra.columns, pd.MultiIndex):
            intra.columns = intra.columns.get_level_values(0)
        if intra.empty or "Close" not in intra.columns:
            return None
        value = float(intra["Close"].iloc[-1])
        return value if np.isfinite(value) and value > 0 else None
    except Exception:
        return None


def calculate_rsi(series, period=14):
    """Wilder-style RSI, with safe handling for flat/up-only/down-only series."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss.ne(0), 100)
    rsi = rsi.where(avg_gain.ne(0), 0)
    rsi = rsi.fillna(50)
    return rsi


def scan_stock(sym, sector_name=""):
    """Original-style breakout + retest scanner, with live quote kept separate."""
    df = get_stock_data(sym)
    if df is None or len(df) < 60:
        return None

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if len(df) < 60:
        return None

    c = df["Close"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    v = df["Volume"].astype(float)

    # Resistance/support use the 35 candles before the most recent 10 candles.
    resistance_window = h.iloc[-45:-10]
    support_window = l.iloc[-45:-10]
    if resistance_window.empty or support_window.empty:
        return None

    resistance = float(resistance_window.max())
    support = float(support_window.min())
    if not np.isfinite(resistance) or resistance <= 0:
        return None

    # Find a breakout close in the latest 10 completed daily candles.
    # FIX-03: Require confirmed breakout volume.
    recent_start = max(0, len(c) - 11)
    breakout_positions = [
        i for i in range(recent_start, len(c) - 1)
        if i >= 20
        and float(c.iloc[i]) > resistance
        and float(v.iloc[i-20:i].mean()) > 0
        and float(v.iloc[i]) >= 1.5 * float(v.iloc[i-20:i].mean())
    ]
    breakout = bool(breakout_positions)
    break_idx = -1
    pullback = False
    retest_low = None

    # Find a breakout candle that is followed by a successful retest.
    # Do not use the latest breakout candle blindly: later closes above
    # resistance can otherwise hide an already-completed pullback.
    band_low = resistance * 0.985
    band_high = resistance * 1.015
    for candidate_idx in breakout_positions:
        for i in range(candidate_idx + 1, len(l)):
            candle_low = float(l.iloc[i])
            candle_close = float(c.iloc[i])
            if i >= len(c) - 3 and band_low <= candle_low <= band_high and candle_close >= resistance:
                break_idx = candidate_idx
                pullback = True
                retest_low = candle_low
                break
        if pullback:
            break

    # Daily indicators are based on daily candles only.
    ema9_series = c.ewm(span=9, adjust=False).mean()
    ema20_series = c.ewm(span=20, adjust=False).mean()
    ema50_series = c.ewm(span=50, adjust=False).mean()
    rsi_series = calculate_rsi(c, 14)

    live_price = get_live_price(sym)
    daily_close = float(c.iloc[-1])
    price = float(live_price) if live_price is not None else daily_close
    if not np.isfinite(price) or price <= 0:
        return None

    # Keep current quote separate; use it only for current price/confirmation.
    ema9 = float(ema9_series.iloc[-2])
    ema20 = float(ema20_series.iloc[-2])
    ema50 = float(ema50_series.iloc[-2])
    rsi = float(rsi_series.iloc[-2])
    prev_close = float(c.iloc[-2])
    change_pct = ((price / prev_close) - 1) * 100 if prev_close else 0.0

    trend_up = price > ema20 and ema20 > ema50
    momentum = price > prev_close
    rsi_ok = 55 <= rsi <= 70
    breakout_holding = breakout and price >= resistance

    # Score is descriptive; BUY requires the core original setup, not a loose score.
    score = sum([
        bool(trend_up),
        bool(breakout),
        bool(pullback),
        bool(momentum),
        bool(rsi_ok),
        bool(breakout_holding)
    ])

    if breakout and pullback and breakout_holding and trend_up and momentum and rsi_ok:
        signal = "BUY"
    elif price < ema20 and ema20 < ema50 and not momentum and rsi < 45:
        signal = "SELL"
    else:
        signal = "WAIT"

    if trend_up:
        trend = "Uptrend"
    elif price < ema20 and ema20 < ema50:
        trend = "Downtrend"
    else:
        trend = "Sideways"

    # Entry uses the retest/resistance level; risk has a minimum 2% floor.
    entry = resistance if breakout else price
if signal == "BUY" and retest_low is not None:
    stop_loss = min(retest_low, entry) * 0.995
    risk = entry - stop_loss
else:
    risk = max(entry - support, price * 0.02)
    stop_loss = entry - risk

target = entry + (risk * 2)

    return {
        "Stock": sym,
        "LTP": round(price, 2),
        "Change %": round(change_pct, 2),
        "Trend": trend,
        "Signal": signal,
        "Entry": round(entry, 2),
        "Target": round(target, 2),
        "Stop Loss": round(stop_loss, 2),
        "Sector": sector_name,
        "_score": int(score),
        "_rsi": round(rsi, 1)
    }

# ==================== HEADER ====================
col_logo, col_search, col_time, col_bell = st.columns([2.5, 3, 1.8, 0.5])

with col_logo:
    st.markdown("""
    <div class="logo-area">
        <div class="logo-icon">📈</div>
        <div class="logo-text">
            <h1>Swift Trade</h1>
            <p>Smart Stock Scanner · এক ক্লিকে সেরা শেয়ার</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_search:
    search_query = st.text_input("search", placeholder="🔍 স্টক নাম লিখুন...", label_visibility="collapsed")

with col_time:
    now = datetime.now()
    st.markdown(f"""
    <div style="text-align:right; padding-top:8px;">
        <div style="font-size:0.9rem; font-weight:600; color:#e0e6ed;">📅 {now.strftime('%d %b %Y')}</div>
        <div style="font-size:0.8rem; color:#7a8ba3;">{now.strftime('%I:%M %p')}</div>
    </div>
    """, unsafe_allow_html=True)

with col_bell:
    st.markdown("<div style='text-align:center; padding-top:10px; font-size:1.4rem;'>🔔</div>", unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ==================== INDEX CARDS ====================
idx_cols = st.columns(4)
index_names = ["NIFTY", "BANKNIFTY", "SENSEX", "INDIA VIX"]

for i, name in enumerate(index_names):
    with idx_cols[i]:
        data = get_index_data(INDEX_SYMBOLS[name])
        if data:
            is_up = data["pct"] >= 0
            change_class = "index-change-up" if is_up else "index-change-down"
            arrow = "▲" if is_up else "▼"
            st.markdown(f"""
            <div class="index-card">
                <div class="index-name">{name}</div>
                <div class="index-value">{data['price']:,.2f}</div>
                <div class="{change_class}">{arrow} {data['change']:+.2f} ({data['pct']:+.2f}%)</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="index-card">
                <div class="index-name">{name}</div>
                <div class="index-value">--</div>
                <div class="index-change-up">Loading...</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ==================== MARKET SELECTOR ====================
st.markdown('<div class="section-label">Market</div>', unsafe_allow_html=True)
asset = st.radio("Market", ["Equity", "F&O", "Forex", "Commodities", "Crypto"], horizontal=True, label_visibility="collapsed", index=0)
# ==================== F&O ENGINE ====================
FNO_UNDERLYINGS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE",
    "MIDCPNIFTY": "NIFTY_MID_SELECT"
}

FNO_REQUIRED_FIELDS = [
    "Strike",
    "Expiry",
    "Option Type",
    "LTP",
    "OI",
    "Change OI",
    "Volume",
    "IV"
            ]

# ==================== COMMODITY ENGINE ====================
COMMODITY_SYMBOLS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "CRUDE OIL": "CL=F",
    "NATURAL GAS": "NG=F"
}

COMMODITY_INDICATORS = [
    "Price",
    "Change %",
    "EMA 9",
    "EMA 20",
    "EMA 50",
    "RSI 14",
    "ATR 14",
    "Volume Ratio"
            ]
# ==================== SECTOR SELECTOR ====================
st.markdown('<div class="section-label">Sector</div>', unsafe_allow_html=True)
all_sectors = list(SECTORS.keys())
selected_sectors = st.multiselect("Sector", ["ALL"] + all_sectors, default=["ALL"], label_visibility="collapsed")

if "ALL" in selected_sectors or not selected_sectors:
    active_sectors = all_sectors
else:
    active_sectors = [s for s in selected_sectors if s != "ALL"]

# ==================== STRATEGY SELECTOR ====================
st.markdown('<div class="section-label">Strategy</div>', unsafe_allow_html=True)
strat_col1, strat_col2 = st.columns([4, 1.2])

with strat_col1:
    strategies = st.multiselect("Strategy", ["Breakout", "Momentum", "Pullback", "Trend"], default=["Breakout", "Momentum"], label_visibility="collapsed")

with strat_col2:
    scan_clicked = st.button("🔍 Scan / Analyze", type="primary", use_container_width=True)

# ==================== AUTO REFRESH CONTROLS ====================
ref_col1, ref_col2, ref_col3 = st.columns([1.5, 1.5, 3])

with ref_col1:
    auto_refresh = st.checkbox("🔄 Auto Refresh", value=st.session_state.auto_refresh, key="auto_refresh_cb")
    st.session_state.auto_refresh = auto_refresh

with ref_col2:
    interval = st.selectbox("Interval", options=[30, 60, 120, 300], format_func=lambda x: f"{x} sec" if x < 60 else f"{x//60} min", index=1, label_visibility="collapsed", key="refresh_interval_select")
    st.session_state.refresh_interval = interval

with ref_col3:
    if st.session_state.auto_refresh:
        elapsed = int(time.time() - st.session_state.last_refresh)
        remaining = max(0, st.session_state.refresh_interval - elapsed)
        st.markdown(f"<div style='padding-top:8px; color:#00e676; font-size:0.85rem;'>⏳ Next refresh in <b>{remaining}s</b></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='padding-top:8px; color:#7a8ba3; font-size:0.85rem;'>Auto refresh off</div>", unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ==================== SCAN LOGIC ====================
if "results" not in st.session_state:
    st.session_state.results = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = set()

should_scan = scan_clicked

if st.session_state.auto_refresh:
    elapsed = time.time() - st.session_state.last_refresh
    if elapsed >= st.session_state.refresh_interval:
        should_scan = True
        st.session_state.last_refresh = time.time()

if should_scan:
    symbols_to_scan = []
    sector_map = {}
    for sec in active_sectors:
        for sym in SECTORS[sec]:
            if sym not in sector_map:
                symbols_to_scan.append(sym)
                sector_map[sym] = sec

    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []

    for i, sym in enumerate(symbols_to_scan):
        status_text.markdown(f"<span style='color:#7a8ba3; font-size:0.85rem;'>Scanning {sym}... ({i+1}/{len(symbols_to_scan)})</span>", unsafe_allow_html=True)
        r = scan_stock(sym, sector_map.get(sym, ""))
        if r:
            results.append(r)
        progress_bar.progress((i + 1) / max(1, len(symbols_to_scan)))

    progress_bar.empty()
    status_text.empty()

    results.sort(key=lambda x: (x["_score"], x["Change %"]), reverse=True)
    st.session_state.results = results
    st.session_state.last_refresh = time.time()
    st.toast(f"✅ {len(results)} টি স্টক স্ক্যান সম্পন্ন!", icon="📈")
results = st.session_state.get("results", [])
b1, b2 = st.columns(2)

# ==================== SUMMARY CARDS ====================
if results:
    total = len(results)
    buy_count = sum(1 for x in results if x["Signal"] == "BUY")
    wait_count = sum(1 for x in results if x["Signal"] == "WAIT")
    sell_count = sum(1 for x in results if x["Signal"] == "SELL")
    uptrend_count = sum(1 for x in results if x["Trend"] == "Uptrend")

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        st.markdown(f"""
        <div class="summary-card blue">
            <div class="summary-title">📊 মোট শেয়ার</div>
            <div class="summary-value">{total}</div>
            <div class="summary-sub">স্ক্যান করা হয়েছে</div>
        </div>
        """, unsafe_allow_html=True)

    with s2:
        pct = (uptrend_count / total * 100) if total else 0

        st.markdown(f"""
        <div class="summary-card green">
            <div class="summary-title">📈 আপ ট্রেন্ড</div>
            <div class="summary-value">{uptrend_count}</div>
            <div class="summary-sub">{pct:.1f}% শেয়ার</div>
        </div>
        """, unsafe_allow_html=True)

    with s3:
        st.markdown(f"""
        <div class="summary-card orange">
            <div class="summary-title">⏳ BUY / WAIT</div>
            <div class="summary-value">{buy_count} / {wait_count}</div>
            <div class="summary-sub">সিগন্যালের সংখ্যা</div>
        </div>
        """, unsafe_allow_html=True)

    with s4:
        st.markdown(f"""
        <div class="summary-card red">
            <div class="summary-title">🔻 SELL</div>
            <div class="summary-value">{sell_count}</div>
            <div class="summary-sub">সতর্কতার সিগন্যাল</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">স্ক্যান রেজাল্ট</div>', unsafe_allow_html=True)

    table_data = results[:6]
    df_display = pd.DataFrame(table_data).drop(
        columns=["_score", "_rsi"], errors="ignore"
    )

    if search_query:
        mask = df_display["Stock"].astype(str).str.contains(
            search_query.strip(), case=False, na=False
        )
        df_display = df_display[mask]

    def color_change(val):
        try:
            return "color: #00e676; font-weight: 700" if float(val) >= 0 else "color: #ff5252; font-weight: 700"
        except (TypeError, ValueError):
            return ""

    def color_signal(val):
        if "BUY" in str(val):
            return "color: #00e676; font-weight: 700"
        elif "WAIT" in str(val):
            return "color: #ffb74d; font-weight: 700"
        elif "SELL" in str(val):
            return "color: #ff5252; font-weight: 700"
        return ""

    if not df_display.empty:
        styled = (
            df_display.style
            .map(color_change, subset=["Change %"])
            .map(color_signal, subset=["Signal"])
        )
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=min(420, 45 + len(df_display) * 38)
        )
    else:
        st.info("আপনার সার্চ অনুযায়ী কোনো স্টক পাওয়া যায়নি।")
else:
    st.info("কোনো রেজাল্ট পাওয়া যায়নি।")

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ==================== BOTTOM SECTION ====================
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>Swift Trade Scanner v1.0</p>",
    unsafe_allow_html=True
        )
        
