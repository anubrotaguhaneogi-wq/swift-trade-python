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

/* Hide Streamlit branding */
#MainMenu, footer, header {visibility: hidden;}
.stDeployButton {display: none;}

/* ===== HEADER ===== */
.header-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.2rem;
    gap: 1rem;
}
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

/* ===== INDEX CARDS ===== */
.index-card {
    background: linear-gradient(145deg, #0f2137, #0c1a2b);
    border: 1px solid #1a3a5c;
    border-radius: 12px;
    padding: 14px 16px;
    height: 100%;
    transition: all 0.2s ease;
}
.index-card:hover {
    border-color: #2a5a8c;
    transform: translateY(-2px);
}
.index-name {
    font-size: 0.72rem;
    color: #7a8ba3;
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.index-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 2px;
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

/* ===== SECTION TITLES ===== */
.section-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #8ba3c7;
    margin-bottom: 8px;
    margin-top: 4px;
}

/* ===== MARKET / SECTOR / STRATEGY BUTTONS ===== */
.stRadio > div {
    gap: 0.4rem !important;
}
.stRadio label {
    background: #0f2137 !important;
    border: 1px solid #1a3a5c !important;
    border-radius: 8px !important;
    padding: 6px 14px !important;
    color: #a0b4cc !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}
.stRadio label[data-checked="true"], 
.stRadio [aria-checked="true"] + label {
    background: linear-gradient(135deg, #00c853, #00a844) !important;
    border-color: #00e676 !important;
    color: white !important;
}

/* Multiselect chips */
.stMultiSelect [data-baseweb="tag"] {
    background: #1a3a5c !important;
    border-radius: 6px !important;
}

/* ===== SUMMARY CARDS ===== */
.summary-card {
    border-radius: 12px;
    padding: 16px 18px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
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
    line-height: 1.1;
}
.summary-sub {
    font-size: 0.75rem;
    color: #7a8ba3;
    margin-top: 2px;
}

/* ===== TABLE STYLING ===== */
.dataframe {
    border: none !important;
}
.dataframe th {
    background: #0f2137 !important;
    color: #8ba3c7 !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    border-bottom: 1px solid #1a3a5c !important;
}
.dataframe td {
    background: #0c1a2b !important;
    color: #e0e6ed !important;
    font-size: 0.85rem !important;
    border-bottom: 1px solid #12253a !important;
}

/* Signal badges */
.badge-buy {
    background: #00c853;
    color: white;
    padding: 3px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.75rem;
}
.badge-wait {
    background: #ff9800;
    color: white;
    padding: 3px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.75rem;
}
.badge-sell {
    background: #f44336;
    color: white;
    padding: 3px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.75rem;
}

/* ===== BOTTOM CARDS ===== */
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

/* ===== BUTTONS ===== */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: none !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

/* Primary scan button */
div[data-testid="stHorizontalBlock"] button[kind="primary"] {
    background: linear-gradient(135deg, #00c853, #00a844) !important;
    color: white !important;
}

/* Metric styling */
[data-testid="stMetricValue"] {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.85rem !important;
}

/* Divider */
hr {
    border-color: #1a3a5c !important;
    margin: 1rem 0 !important;
}

/* Caption */
.stCaption {
    color: #5a6f8a !important;
}
</style>
""", unsafe_allow_html=True)

# ==================== DATA ====================
SECTORS = {
    "Bank": ["KOTAKBANK", "ICICIBANK", "SBIN", "HDFCBANK", "AXISBANK"],
    "IT": ["TCS", "HCLTECH", "INFY", "WIPRO", "TECHM"],
    "Auto": ["M&M", "MARUTI", "BAJAJ-AUTO", "EICHERMOT", "TATAMOTORS"],
    "Pharma": ["DRREDDY", "DIVISLAB", "SUNPHARMA", "CIPLA"],
    "Energy": ["RELIANCE", "ONGC", "COALINDIA", "NTPC", "POWERGRID"],
    "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA"],
    "Metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL"],
    "PSU": ["BEL", "HAL", "IRFC", "RVNL", "RECLTD"],
    "Defence": ["HAL", "BEL", "BHEL", "MAZDOCK", "COCHINSHIP"],
    "Others": ["ASIANPAINT", "TITAN", "TRENT", "ADANIENT", "ZOMATO"]
}

INDEX_SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "INDIA VIX": "^INDIAVIX"
}

@st.cache_data(ttl=300)
def get_index_data(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 2:
            return None
        price = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2])
        change = price - prev
        pct = (change / prev) * 100
        return {"price": price, "change": change, "pct": pct}
    except:
        return None

@st.cache_data(ttl=900)
def get_stock_data(sym):
    try:
        df = yf.download(sym + ".NS", period="1y", interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except:
        return pd.DataFrame()

def scan_stock(sym, sector_name=""):
    df = get_stock_data(sym)
    if len(df) < 60:
        return None

    c, h, l, v = df.Close, df.High, df.Low, df.Volume
    price = float(c.iloc[-1])
    prev_close = float(c.iloc[-2])
    change_pct = (price / prev_close - 1) * 100

    ema20 = c.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = c.ewm(span=50, adjust=False).mean().iloc[-1]

    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = float((100 - 100 / (1 + gain / loss.replace(0, pd.NA))).fillna(50).iloc[-1])

    resistance = float(h.iloc[-21:-1].max())
    support = float(l.iloc[-21:-1].min())
    avg_vol = float(v.iloc[-21:-1].mean())
    vol_ratio = float(v.iloc[-1]) / avg_vol if avg_vol else 0

    trend_up = price > ema20 > ema50
    breakout = price > resistance
    momentum = price > prev_close
    volume_ok = vol_ratio >= 1.0
    rsi_ok = rsi >= 50

    score = sum([trend_up, breakout, momentum, volume_ok, rsi_ok])

    if score >= 4:
        signal = "BUY"
    elif score >= 2:
        signal = "WAIT"
    else:
        signal = "SELL"

    if trend_up:
        trend = "Uptrend"
    elif price < ema20 and ema20 < ema50:
        trend = "Downtrend"
    else:
        trend = "Sideways"

    trigger = resistance if breakout else price
    risk = max(trigger - support, price * 0.02)

    return {
        "Stock": sym,
        "LTP": round(price, 2),
        "Change %": round(change_pct, 2),
        "Trend": trend,
        "Signal": signal,
        "Entry": round(trigger, 2),
        "Target": round(trigger + risk * 2, 2),
        "Stop Loss": round(trigger - risk, 2),
        "Sector": sector_name,
        "_score": score,
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
    search_query = st.text_input(
        "search",
        placeholder="🔍 স্টক নাম লিখুন...",
        label_visibility="collapsed"
    )

with col_time:
    now = datetime.now()
    st.markdown(f"""
    <div style="text-align:right; padding-top:8px;">
        <div style="font-size:0.9rem; font-weight:600; color:#e0e6ed;">📅 {now.strftime('%d %b %Y')}</div>
        <div style="font-size:0.8rem; color:#7a8ba3;">{now.strftime('%I:%M %p')}</div>
    </div>
    """, unsafe_allow_html=True)

with col_bell:
    st.markdown("""
    <div style="text-align:center; padding-top:10px; font-size:1.4rem;">
        🔔
    </div>
    """, unsafe_allow_html=True)

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
asset = st.radio(
    "Market",
    ["Equity", "F&O", "Forex", "Commodities", "Crypto"],
    horizontal=True,
    label_visibility="collapsed",
    index=0
)

if asset != "Equity":
    st.info(f"🚧 **{asset}** মডিউল শীঘ্রই আসছে। এখন শুধু Equity স্ক্যানার চালু আছে।")
    st.stop()

# ==================== SECTOR SELECTOR ====================
st.markdown('<div class="section-label">Sector</div>', unsafe_allow_html=True)
all_sectors = list(SECTORS.keys())
selected_sectors = st.multiselect(
    "Sector",
    ["ALL"] + all_sectors,
    default=["ALL"],
    label_visibility="collapsed"
)

if "ALL" in selected_sectors or not selected_sectors:
    active_sectors = all_sectors
else:
    active_sectors = [s for s in selected_sectors if s != "ALL"]

# ==================== STRATEGY SELECTOR ====================
st.markdown('<div class="section-label">Strategy</div>', unsafe_allow_html=True)
strat_col1, strat_col2 = st.columns([4, 1.2])

with strat_col1:
    strategies = st.multiselect(
        "Strategy",
        ["Breakout", "Momentum", "Pullback", "Trend"],
        default=["Breakout", "Momentum"],
        label_visibility="collapsed"
    )

with strat_col2:
    scan_clicked = st.button("🔍 Scan / Analyze", type="primary", use_container_width=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ==================== SCAN LOGIC ====================
if "results" not in st.session_state:
    st.session_state.results = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = set()

if scan_clicked:
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
        progress_bar.progress((i + 1) / len(symbols_to_scan))

    progress_bar.empty()
    status_text.empty()

    results.sort(key=lambda x: (x["_score"], x["Change %"]), reverse=True)
    st.session_state.results = results
    st.toast(f"✅ {len(results)} টি স্টক স্ক্যান সম্পন্ন!", icon="📈")

results = st.session_state.results

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
            <div class="summary-value">{uptrend_count} <span style="font-size:0.9rem;color:#00e676">({pct:.1f}%)</span></div>
            <div class="summary-sub">Bullish stocks</div>
        </div>
        """, unsafe_allow_html=True)

    with s3:
        pct = (wait_count / total * 100) if total else 0
        st.markdown(f"""
        <div class="summary-card orange">
            <div class="summary-title">⚡ সাইডওয়েজ</div>
            <div class="summary-value">{wait_count} <span style="font-size:0.9rem;color:#ffb74d">({pct:.1f}%)</span></div>
            <div class="summary-sub">Neutral zone</div>
        </div>
        """, unsafe_allow_html=True)

    with s4:
        pct = (sell_count / total * 100) if total else 0
        st.markdown(f"""
        <div class="summary-card red">
            <div class="summary-title">📉 ডাউন ট্রেন্ড</div>
            <div class="summary-value">{sell_count} <span style="font-size:0.9rem;color:#ff8a80">({pct:.1f}%)</span></div>
            <div class="summary-sub">Bearish signals</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ==================== SCAN RESULTS TABLE ====================
    st.markdown("### 📊 Scan Results")

    # Sort option
    sort_col1, sort_col2 = st.columns([6, 1.5])
    with sort_col2:
        sort_by = st.selectbox(
            "Sort",
            ["Best Signal", "Highest Change %", "Lowest Change %", "Stock Name"],
            label_visibility="collapsed"
        )

    # Apply sorting
    display_results = results.copy()
    if sort_by == "Highest Change %":
        display_results.sort(key=lambda x: x["Change %"], reverse=True)
    elif sort_by == "Lowest Change %":
        display_results.sort(key=lambda x: x["Change %"])
    elif sort_by == "Stock Name":
        display_results.sort(key=lambda x: x["Stock"])
    else:
        display_results.sort(key=lambda x: (x["_score"], x["Change %"]), reverse=True)

    # Filter by search
    if search_query:
        display_results = [r for r in display_results if search_query.upper() in r["Stock"]]

    # Build table data
    table_data = []
    for idx, r in enumerate(display_results, 1):
        signal_emoji = {"BUY": "🟢 BUY", "WAIT": "🟠 WAIT", "SELL": "🔴 SELL"}[r["Signal"]]
        change_str = f"+{r['Change %']:.2f}%" if r["Change %"] >= 0 else f"{r['Change %']:.2f}%"
        table_data.append({
            "#": idx,
            "Stock Name": r["Stock"],
            "LTP (₹)": f"{r['LTP']:,.0f}" if r["LTP"] >= 100 else f"{r['LTP']:.2f}",
            "Change %": change_str,
            "Trend": r["Trend"],
            "Signal": signal_emoji,
            "Entry (₹)": f"{r['Entry']:,.0f}",
            "Target (₹)": f"{r['Target']:,.0f}",
            "Stop Loss (₹)": f"{r['Stop Loss']:,.0f}",
            "Sector": r["Sector"]
        })

    if table_data:
        df_display = pd.DataFrame(table_data)

        # Color styling for Change %
        def color_change(val):
            if isinstance(val, str):
                if val.startswith("+"):
                    return "color: #00e676; font-weight: 600"
                elif val.startswith("-"):
                    return "color: #ff5252; font-weight: 600"
            return ""

        def color_signal(val):
            if "BUY" in str(val):
                return "color: #00e676; font-weight: 700"
            elif "WAIT" in str(val):
                return "color: #ffb74d; font-weight: 700"
            elif "SELL" in str(val):
                return "color: #ff5252; font-weight: 700"
            return ""

        styled = df_display.style.map(color_change, subset=["Change %"]).map(color_signal, subset=["Signal"])

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=min(420, 45 + len(table_data) * 38)
        )
    else:
        st.info("কো
