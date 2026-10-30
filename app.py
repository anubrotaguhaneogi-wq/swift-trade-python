import streamlit as st
import yfinance as yf
import pandas as pd


# ============================================================
# SWIFT TRADE — PROFESSIONAL SCANNER ENGINE v1
# Step 1 + Step 2
# RSI + Breakout + Pullback + ATR + Volume
# Trigger + Target 1/2/3 + Stop Loss + Risk/Reward
# ============================================================


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Swift Trade",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PROFESSIONAL DARK UI
# ============================================================
st.markdown("""
<style>

.stApp {
    background:
        radial-gradient(circle at top left, #10233d 0%, #07111f 35%, #030912 100%);
    color: #f5f7fa;
}

.block-container {
    max-width: 1500px;
    padding-top: 1.2rem;
}

h1, h2, h3 {
    color: #ffffff !important;
}

[data-testid="stMetric"] {
    background: rgba(8, 25, 45, 0.85);
    border: 1px solid #164d7a;
    border-radius: 14px;
    padding: 14px;
}

[data-testid="stMetricValue"] {
    color: #00e676 !important;
}

.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    border: 1px solid #1769aa;
    background: #092544;
    color: white;
}

.stButton > button:hover {
    border-color: #00e676;
    color: #00e676;
}

div[data-baseweb="select"] > div {
    background-color: #0b1728;
    border-color: #1d527d;
}

div[data-baseweb="input"] > div {
    background-color: #0b1728;
    border-color: #1d527d;
}

.swift-card {
    background: linear-gradient(145deg, #0a1d33, #06111f);
    border: 1px solid #174d78;
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 15px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.25);
}

.buy {
    color: #00e676;
    font-weight: 800;
    font-size: 20px;
}

.wait {
    color: #ffca28;
    font-weight: 800;
    font-size: 20px;
}

.sell {
    color: #ff5252;
    font-weight: 800;
    font-size: 20px;
}

.small-muted {
    color: #9fb0c0;
    font-size: 13px;
}

.check-ok {
    color: #00e676;
}

.check-fail {
    color: #ff5252;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# ASSET / SECTOR DATABASE
# ============================================================

SECTORS = {
    "Bank": [
        "KOTAKBANK",
        "ICICIBANK",
        "SBIN",
        "HDFCBANK",
        "AXISBANK",
        "INDUSINDBK",
        "BANKBARODA",
    ],

    "IT": [
        "TCS",
        "HCLTECH",
        "INFY",
        "WIPRO",
        "TECHM",
        "LTIM",
        "MPHASIS",
    ],

    "Auto": [
        "M&M",
        "MARUTI",
        "BAJAJ-AUTO",
        "EICHERMOT",
        "TATAMOTORS",
        "HEROMOTOCO",
    ],

    "Pharma": [
        "DRREDDY",
        "DIVISLAB",
        "SUNPHARMA",
        "CIPLA",
        "APOLLOHOSP",
        "LUPIN",
    ],

    "Energy": [
        "RELIANCE",
        "ONGC",
        "COALINDIA",
        "NTPC",
        "POWERGRID",
        "BPCL",
    ],

    "FMCG": [
        "ITC",
        "HINDUNILVR",
        "NESTLEIND",
        "BRITANNIA",
        "TATACONSUM",
        "DABUR",
    ],

    "Metal": [
        "TATASTEEL",
        "JSWSTEEL",
        "HINDALCO",
        "VEDL",
        "JINDALSTEL",
    ],

    "Infra": [
        "LT",
        "ADANIPORTS",
        "DLF",
        "ULTRACEMCO",
        "GRASIM",
    ],

    "Realty": [
        "DLF",
        "GODREJPROP",
        "OBEROIRLTY",
        "LODHA",
    ],

    "PSU": [
        "BEL",
        "HAL",
        "IRFC",
        "RVNL",
        "RECLTD",
        "PFC",
    ],

    "Defence": [
        "HAL",
        "BEL",
        "BHEL",
        "MAZDOCK",
        "COCHINSHIP",
    ],

    "Others": [
        "ASIANPAINT",
        "TITAN",
        "TRENT",
        "ADANIENT",
        "ZOMATO",
        "PIDILITIND",
    ],
}


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)

    rsi_value = 100 - (100 / (1 + rs))

    return rsi_value.fillna(50)


def calculate_atr(df, period=14):
    previous_close = df["Close"].shift(1)

    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - previous_close).abs()
    tr3 = (df["Low"] - previous_close).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    atr = true_range.rolling(period).mean()

    return atr


# ============================================================
# DOWNLOAD MARKET DATA
# ============================================================

@st.cache_data(ttl=900)
def get_data(sym):

    try:

        df = yf.download(
            sym + ".NS",
            period="1y",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        missing = [
            c for c in required
            if c not in df.columns
        ]

        if missing:
            return pd.DataFrame()

        df = df[required].copy()

        df = df.dropna()

        return df

    except Exception:
        return pd.DataFrame()


# ============================================================
# MAIN PROFESSIONAL ANALYSIS ENGINE
# ============================================================

def analyze(
    sym,
    rsi_min=50,
    pullback_pct=1.5,
    volume_multiplier=1.0,
    atr_multiplier=1.5,
    strategy="Professional Breakout"
):

    df = get_data(sym)

    if df.empty or len(df) < 80:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    last_price = float(close.iloc[-1])

    # --------------------------------------------------------
    # INDICATORS
    # --------------------------------------------------------

    rsi_series = calculate_rsi(close, 14)
    atr_series = calculate_atr(df, 14)

    rsi_value = float(rsi_series.iloc[-1])
    atr_value = float(atr_series.iloc[-1])

    if pd.isna(atr_value) or atr_value <= 0:
        return None

    # --------------------------------------------------------
    # MOVING AVERAGES
    # --------------------------------------------------------

    ema20 = float(
        close.ewm(span=20, adjust=False).mean().iloc[-1]
    )

    ema50 = float(
        close.ewm(span=50, adjust=False).mean().iloc[-1]
    )

    trend_up = last_price > ema20 and ema20 > ema50

    # --------------------------------------------------------
    # RESISTANCE / SUPPORT
    # --------------------------------------------------------

    lookback = 20

    resistance = float(
        high.iloc[-lookback-1:-1].max()
    )

    support = float(
        low.iloc[-lookback-1:-1].min()
    )

    # --------------------------------------------------------
    # BREAKOUT
    # --------------------------------------------------------

    breakout = last_price > resistance

    # --------------------------------------------------------
    # PULLBACK
    # --------------------------------------------------------

    pullback_zone = resistance * (
        1 - pullback_pct / 100
    )

    recent_low = float(
        low.iloc[-5:].min()
    )

    pullback = (
        recent_low <= resistance
        and recent_low >= pullback_zone
        and last_price >= resistance
    )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    rising = (
        last_price > float(close.iloc[-2])
        and last_price > float(close.iloc[-4])
    )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    avg_volume = float(
        volume.iloc[-21:-1].mean()
    )

    current_volume = float(
        volume.iloc[-1]
    )

    volume_ratio = (
        current_volume / avg_volume
        if avg_volume > 0
        else 0
    )

    volume_ok = volume_ratio >= volume_multiplier

    # --------------------------------------------------------
    # PRICE CHANGE
    # --------------------------------------------------------

    previous_close = float(
        close.iloc[-2]
    )

    change_pct = (
        (last_price / previous_close) - 1
    ) * 100

    # --------------------------------------------------------
    # TRIGGER PRICE
    # --------------------------------------------------------

    trigger_price = resistance + (
        atr_value * 0.10
    )

    # --------------------------------------------------------
    # STOP LOSS
    # --------------------------------------------------------

    atr_stop = trigger_price - (
        atr_value * atr_multiplier
    )

    structural_stop = support

    stop_loss = min(
        atr_stop,
        structural_stop
    )

    if stop_loss >= trigger_price:
        stop_loss = trigger_price - atr_value

    risk = trigger_price - stop_loss

    if risk <= 0:
        return None

    # --------------------------------------------------------
    # TARGETS
    # --------------------------------------------------------

    target1 = trigger_price + (risk * 1.0)
    target2 = trigger_price + (risk * 2.0)
    target3 = trigger_price + (risk * 3.0)

    # --------------------------------------------------------
    # CONDITIONS / SCORE  (Strategy-aware)
    # --------------------------------------------------------

    checks = {
        "RSI": rsi_value >= rsi_min,
        "Trend": trend_up,
        "Resistance Break": breakout,
        "Pullback": pullback,
        "Momentum": rising,
        "Volume": volume_ok,
    }

    # Strategy-specific weighting / filtering
    if strategy == "Pullback":
        # Prioritize pullback + trend
        required_keys = ["Trend", "Pullback", "RSI"]
    elif strategy == "RSI Momentum":
        required_keys = ["RSI", "Momentum", "Trend"]
    elif strategy == "Trend + Volume":
        required_keys = ["Trend", "Volume", "Momentum"]
    elif strategy == "Professional Breakout":
        required_keys = ["Resistance Break", "Trend", "Volume", "RSI"]
    else:  # Custom
        required_keys = list(checks.keys())

    score = sum(bool(checks[k]) for k in required_keys if k in checks)
    total_checks = len(required_keys)

    confidence = (score / total_checks) * 100 if total_checks > 0 else 0

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    if score >= max(4, total_checks - 1):
        signal = "BUY"
    elif score >= max(2, total_checks // 2):
        signal = "WAIT"
    else:
        signal = "SELL"

    # --------------------------------------------------------
    # RISK / REWARD
    # --------------------------------------------------------

    rr1 = (
        (target1 - trigger_price) / risk
    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {

        "sym": sym,

        "price": last_price,

        "chg": change_pct,

        "rsi": rsi_value,

        "atr": atr_value,

        "volume_ratio": volume_ratio,

        "res": resistance,

        "sup": support,

        "trigger": trigger_price,

        "target1": target1,

        "target2": target2,

        "target3": target3,

        "stop_loss": stop_loss,

        "risk_reward": rr1,

        "score": score,

        "total_checks": total_checks,

        "confidence": confidence,

        "signal": signal,

        "checks": checks,

        "ema20": ema20,

        "ema50": ema50,
    }


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    # 📈 Swift Trade
    ### এক ক্লিকে Technical Market Scanner
    """
)

st.caption(
    "দিনের শেষের Market Data • Technical Analysis • Trigger / Target / Stop Loss"
)


# ============================================================
# TOP MARKET STYLE CARDS
# ============================================================

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Scanner Engine",
        "ONLINE",
        "Ready"
    )

with c2:
    st.metric(
        "Data Source",
        "Yahoo Finance",
        "15 min cache"
    )

with c3:
    st.metric(
        "Indicators",
        "6",
        "Active"
    )

with c4:
    st.metric(
        "Trade Levels",
        "T1 • T2 • T3",
        "Active"
    )


# ============================================================
# ASSET CATEGORY
# ============================================================

st.subheader("মার্কেট টাইপ নির্বাচন করুন")

asset_type = st.radio(
    "Asset Type",
    [
        "Equity",
        "F&O",
        "Forex",
        "Commodities",
        "Crypto",
        "Community"
    ],
    horizontal=True
)


if asset_type != "Equity":

    st.info(
        f"{asset_type} module-এর data engine পরবর্তী ধাপে যুক্ত হবে। "
        "বর্তমানে Equity Scanner সম্পূর্ণভাবে active."
    )


# ============================================================
# EQUITY SECTOR
# ============================================================

if asset_type == "Equity":

    st.subheader("১. Sector নির্বাচন করুন")

    picked = st.multiselect(
        "Sector",
        list(SECTORS.keys()),
        default=list(SECTORS.keys())
    )

else:

    picked = []


# ============================================================
# SCANNER SETTINGS
# ============================================================

st.subheader("২. Scanner Conditions")

col1, col2, col3, col4 = st.columns(4)

with col1:

    rsi_min = st.number_input(
        "RSI এর উপরে",
        min_value=1.0,
        max_value=99.0,
        value=50.0,
        step=1.0
    )

with col2:

    pullback_pct = st.number_input(
        "Pullback দূরত্ব %",
        min_value=0.1,
        max_value=10.0,
        value=1.5,
        step=0.1
    )

with col3:

    volume_multiplier = st.number_input(
        "Volume > Average",
        min_value=0.1,
        max_value=10.0,
        value=1.0,
        step=0.1
    )

with col4:

    atr_multiplier = st.number_input(
        "ATR Stop Multiplier",
        min_value=0.5,
        max_value=5.0,
        value=1.5,
        step=0.1
    )


# ============================================================
# STRATEGY
# ============================================================

st.subheader("৩. Strategy")

strategy = st.selectbox(
    "Strategy Template",
    [
        "Professional Breakout",
        "Pullback",
        "RSI Momentum",
        "Trend + Volume",
        "Custom"
    ]
)


# ============================================================
# ANALYZE BUTTON
# ============================================================

analyze_button = st.button(
    "🔍 SCAN / ANALYZE",
    type="primary",
    use_container_width=True
)


# ============================================================
# SCANNER
# ============================================================

if analyze_button:

    if asset_type != "Equity":

        st.warning(
            f"{asset_type} scanner এখনো active হয়নি। "
            "আগে Equity engine যাচাই করা হবে।"
        )

    elif not picked:

        st.warning(
            "কমপক্ষে একটি Sector নির্বাচন করুন।"
        )

    else:

        symbols = []

        for sector in picked:
            symbols.extend(
                SECTORS[sector]
            )

        symbols = list(
            dict.fromkeys(symbols)
        )

        results = []

        progress = st.progress(0)

        status = st.empty()

        total = len(symbols)

        for index, symbol in enumerate(symbols):

            status.write(
                f"Scanning {symbol}..."
            )

            try:

                result = analyze(
                    symbol,
                    rsi_min=rsi_min,
                    pullback_pct=pullback_pct,
                    volume_multiplier=volume_multiplier,
                    atr_multiplier=atr_multiplier,
                    strategy=strategy
                )

                if result:
                    results.append(result)

            except Exception:

                pass

            progress.progress(
                (index + 1) / total
            )

        progress.empty()
        status.empty()

        # ----------------------------------------------------
        # SORT
        # ----------------------------------------------------

        results.sort(
            key=lambda x: (
                x["score"],
                x["confidence"],
                x["rsi"]
            ),
            reverse=True
        )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        buy_count = sum(
            1 for x in results
            if x["signal"] == "BUY"
        )

        wait_count = sum(
            1 for x in results
            if x["signal"] == "WAIT"
        )

        sell_count = sum(
            1 for x in results
            if x["signal"] == "SELL"
        )

        total_count = len(results)

        st.subheader("Scanner Summary")

        s1, s2, s3, s4 = st.columns(4)

        with s1:
            st.metric(
                "Total Stocks",
                total_count
            )

        with s2:
            st.metric(
                "BUY",
                buy_count
            )

        with s3:
            st.metric(
                "WAIT",
                wait_count
            )

        with s4:
            st.metric(
                "SELL",
                sell_count
            )

        # ----------------------------------------------------
        # RESULT TABLE
        # ----------------------------------------------------

        st.subheader(
            "Professional Scan Results"
        )

        if results:

            table_rows = []

            for r in results:

                table_rows.append({

                    "Stock":
                        r["sym"],

                    "LTP":
                        round(r["price"], 2),

                    "Change %":
                        round(r["chg"], 2),

                    "RSI":
                        round(r["rsi"], 1),

                    "Trigger":
                        round(r["trigger"], 2),

                    "Target 1":
                        round(r["target1"], 2),

                    "Target 2":
                        round(r["target2"], 2),

                    "Target 3":
                        round(r["target3"], 2),

                    "Stop Loss":
                        round(r["stop_loss"], 2),

                    "R:R":
                        f"1:{r['risk_reward']:.1f}",

                    "Score":
                        f"{r['score']}/{r['total_checks']}",

                    "Confidence":
                        f"{r['confidence']:.0f}%",

                    "Signal":
                        r["signal"],
                })

            result_df = pd.DataFrame(
                table_rows
            )

            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=
