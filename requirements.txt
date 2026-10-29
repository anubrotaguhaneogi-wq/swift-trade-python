import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Swift Trade", layout="centered")

SECTORS = {
    "Bank": ["KOTAKBANK", "ICICIBANK", "SBIN", "HDFCBANK", "AXISBANK"],
    "IT": ["TCS", "HCLTECH", "INFY", "WIPRO"],
    "Auto": ["M&M", "MARUTI", "BAJAJ-AUTO", "EICHERMOT"],
    "Pharma": ["DRREDDY", "DIVISLAB", "SUNPHARMA", "CIPLA"],
    "Energy": ["RELIANCE", "ONGC", "COALINDIA", "NTPC"],
    "FMCG": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA"],
}


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


@st.cache_data(ttl=900)
def get_data(sym):
    df = yf.download(sym + ".NS", period="1y", interval="1d",
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


def analyze(sym, rsi_min, pct, res_len=20, look=10):
    df = get_data(sym)
    n = len(df)
    if n < 60:
        return None
    start = n - look
    res = df["High"].iloc[start - res_len:start].max()
    sup = df["Low"].iloc[start - res_len:start].min()
    close = df["Close"]

    # ব্রেকআউট
    b = None
    for i in range(start, n):
        if close.iloc[i] > res:
            b = i
            break
    broken = b is not None and close.iloc[-1] > res

    # পুলব্যাক
    pullback = False
    if broken:
        zone = res * (1 + pct / 100)
        for j in range(b + 1, n):
            if df["Low"].iloc[j] <= zone and close.iloc[j] >= res:
                pullback = True
                break

    r = rsi(close).iloc[-1]
    rising = close.iloc[-1] > close.iloc[-2] and close.iloc[-1] > close.iloc[-4]
    chg = (close.iloc[-1] / close.iloc[-2] - 1) * 100

    return {
        "sym": sym, "price": close.iloc[-1], "chg": chg,
        "res": res, "sup": sup, "rsi": r,
        "checks": {
            "RSI": r > rsi_min,
            "Resistance ভেঙেছে": broken,
            "Pullback": pullback,
            "আবার উঠছে": rising,
        },
    }


st.title("Swift Trade")
st.caption("এক ক্লিকে বিশ্লেষণ (দিনের শেষের ডেটা)")

st.subheader("১. সেক্টর বেছে নিন")
picked = st.multiselect("সেক্টর", list(SECTORS), default=list(SECTORS))

st.subheader("২. আপনার শর্ত")
rsi_min = st.number_input("RSI এর উপরে", value=50)
pct = st.number_input("Pullback দূরত্ব %", value=1.5)

if st.button("Analyze", type="primary"):
    syms = [s for sec in picked for s in SECTORS[sec]]
    results = []
    bar = st.progress(0)
    for k, s in enumerate(syms):
        try:
            r = analyze(s, rsi_min, pct)
            if r:
                results.append(r)
        except Exception:
            pass
        bar.progress((k + 1) / len(syms))
    bar.empty()

    results.sort(key=lambda x: sum(x["checks"].values()), reverse=True)
    for r in results:
        score = sum(r["checks"].values())
        icon = "🟢" if score == 4 else "🟠" if score >= 1 else "⚪"
        with st.container(border=True):
            st.markdown(f"**{icon} {r['sym']}** — {r['price']:.2f} ({r['chg']:+.2f}%)")
            st.caption(f"Resistance {r['res']:.2f} | Support {r['sup']:.2f} | {score}/4 শর্ত")
            st.write(" ".join(
                f"{'✅' if ok else '❌'} {name}" + (f" {r['rsi']:.0f}" if name == "RSI" else "")
                for name, ok in r["checks"].items()
            ))
