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
    try:
        df = yf.download(sym + ".NS", period="1y", interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        try:
            intra = yf.download(sym + ".NS", period="5d", interval="5m", progress=False, auto_adjust=True)
            if isinstance(intra.columns, pd.MultiIndex):
                intra.columns = intra.columns.get_level_values(0)
            if len(intra) > 0:
                latest_price = float(intra["Close"].iloc[-1])
                df.iloc[-1, df.columns.get_loc("Close")] = latest_price
        except:
            pass
        return df
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

    ema20 = float(c.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(c.ewm(span=50, adjust=False).mean().iloc[-1])

    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi_series = (100 - 100 / (1 + gain / loss.replace(0, pd.NA))).fillna(50)
    rsi = float(rsi_series.iloc[-1])

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

if asset != "Equity":
    st.info(f"🚧 **{asset}** মডিউল শীঘ্রই আসছে। এখন শুধু Equity স্ক্যানার চালু আছে।")
    st.stop()

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
        progress_bar.progress((i + 1) / len(symbols_to_scan))

    progress_bar.empty()
    status_text.empty()

    results.sort(key=lambda x: (x["_score"], x["Change %"]), reverse=True)
    st.session_state.results = results
    st.session_state.last_refresh = time.time()
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

    sort_col1, sort_col2 = st.columns([6, 1.5])
    with sort_col2:
        sort_by = st.selectbox("Sort", ["Best Signal", "Highest Change %", "Lowest Change %", "Stock Name"], label_visibility="collapsed")

    display_results = results.copy()
    if sort_by == "Highest Change %":
        display_results.sort(key=lambda x: x["Change %"], reverse=True)
    elif sort_by == "Lowest Change %":
        display_results.sort(key=lambda x: x["Change %"])
    elif sort_by == "Stock Name":
    
        display_results.sort(key=lambda x: x["Stock"])
    else:
        display_results.sort(key=lambda x: (x["_score"], x["Change %"]), reverse=True)

    if search_query:
        display_results = [r for r in display_results if search_query.upper() in r["Stock"]]

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
        st.dataframe(styled, use_container_width=True, hide_index=True, height=min(420, 45 + len(table_data) * 38))
    else:
        st.info("কোনো রেজাল্ট পাওয়া যায়নি।")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ==================== BOTTOM SECTION ====================
    b1, b2 = st.columns(2)

with b1:
    st.markdown("""
    <div class="bottom-card">
        <h4>💡 Swift Tip</h4>
        <p style="font-size:0.85rem; color:#8ba3c7; margin:0;">
            ব্রেকআউট এবং ভালো ভলিউম থাকা স্টকগুলোতে ইন্ট্রাডে ট্রেডের সম্ভাবনা বেশি থাকে। সবসময় স্টপ লস মেনে চলুন।
        </p>
    </div>
    """, unsafe_allow_html=True)

with b2:
    st.markdown("""
    <div class="bottom-card">
        <h4>⚡ Quick Scanner Info</h4>
        <p style="font-size:0.85rem; color:#8ba3c7; margin:0;">
            এই স্ক্যানারটি প্রতিদিনের ট্রেন্ড, RSI এবং মুভিং এভারেজ বিশ্লেষণ করে রিয়েল-টাইম সিগন্যাল প্রদান করে।
        </p>
    </div>
    """, unsafe_allow_html=True)
        
