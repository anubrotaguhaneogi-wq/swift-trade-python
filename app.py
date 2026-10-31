import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Swift Trade", page_icon="📈", layout="wide")

st.markdown("""
<style>
.stApp{background:linear-gradient(135deg,#07111f,#10233d);color:white}
.block-container{max-width:1200px;padding-top:1rem}
.card{background:#0b1d31;border:1px solid #174d78;border-radius:14px;padding:16px;margin:8px 0}
.buy{color:#00e676;font-weight:800}.wait{color:#ffca28;font-weight:800}
.sell{color:#ff5252;font-weight:800}
</style>
""", unsafe_allow_html=True)

SECTORS = {
"Bank":["KOTAKBANK","ICICIBANK","SBIN","HDFCBANK","AXISBANK"],
"IT":["TCS","HCLTECH","INFY","WIPRO","TECHM"],
"Auto":["M&M","MARUTI","BAJAJ-AUTO","EICHERMOT","TATAMOTORS"],
"Pharma":["DRREDDY","DIVISLAB","SUNPHARMA","CIPLA"],
"Energy":["RELIANCE","ONGC","COALINDIA","NTPC","POWERGRID"],
"FMCG":["ITC","HINDUNILVR","NESTLEIND","BRITANNIA"],
"Metal":["TATASTEEL","JSWSTEEL","HINDALCO","VEDL"],
"PSU":["BEL","HAL","IRFC","RVNL","RECLTD"],
"Defence":["HAL","BEL","BHEL","MAZDOCK","COCHINSHIP"],
"Others":["ASIANPAINT","TITAN","TRENT","ADANIENT","ZOMATO"]
}

@st.cache_data(ttl=900)
def data(sym):
    try:
        df=yf.download(sym+".NS",period="1y",interval="1d",
                       progress=False,auto_adjust=True)
        if isinstance(df.columns,pd.MultiIndex):
            df.columns=df.columns.get_level_values(0)
        return df[["Open","High","Low","Close","Volume"]].dropna()
    except:
        return pd.DataFrame()

def scan(sym):
    df=data(sym)
    if len(df)<60:return None
    c,h,l,v=df.Close,df.High,df.Low,df.Volume
    price=float(c.iloc[-1])
    ema20=c.ewm(span=20,adjust=False).mean().iloc[-1]
    ema50=c.ewm(span=50,adjust=False).mean().iloc[-1]
    delta=c.diff(); gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rsi=float((100-100/(1+gain/loss.replace(0,pd.NA))).fillna(50).iloc[-1])
    resistance=float(h.iloc[-21:-1].max())
    support=float(l.iloc[-21:-1].min())
    avgv=float(v.iloc[-21:-1].mean())
    vr=float(v.iloc[-1]/avgv) if avgv else 0
    trend=price>ema20>ema50
    breakout=price>resistance
    momentum=price>float(c.iloc[-2])
    volume=vr>=1
    score=sum([trend,breakout,momentum,volume,rsi>=50])
    signal="BUY" if score>=4 else "WAIT" if score>=2 else "SELL"
    trigger=resistance
    risk=max(trigger-support,price*.02)
    return {
        "Stock":sym,"LTP":round(price,2),
        "Change %":round((price/float(c.iloc[-2])-1)*100,2),
        "Trend":"UP" if trend else "DOWN",
        "Signal":signal,
        "Entry":round(trigger,2),
        "Target":round(trigger+risk*2,2),
        "Stop Loss":round(trigger-risk,2),
        "_score":score
    }

st.title("📈 Swift Trade")
st.caption("Simple Technical Market Scanner")

asset=st.radio("Market",["Equity","F&O","Forex","Commodities","Crypto"],horizontal=True)

if asset!="Equity":
    st.info(f"{asset} module is coming next.")
else:
    sectors=st.multiselect("Sector",list(SECTORS),default=list(SECTORS))
    if st.button("🔍 SCAN MARKET",type="primary",use_container_width=True):
        symbols=list(dict.fromkeys(x for s in sectors for x in SECTORS[s]))
        bar=st.progress(0); results=[]
        for i,sym in enumerate(symbols):
            r=scan(sym)
            if r: results.append(r)
            bar.progress((i+1)/len(symbols))
        bar.empty()
        results.sort(key=lambda x:(x["_score"],x["Change %"]),reverse=True)
        st.session_state.results=results

results=st.session_state.get("results",[])
if results:
    buy=sum(x["Signal"]=="BUY" for x in results)
    wait=sum(x["Signal"]=="WAIT" for x in results)
    sell=sum(x["Signal"]=="SELL" for x in results)
    a,b,c,d=st.columns(4)
    a.metric("Stocks",len(results)); b.metric("BUY",buy)
    c.metric("WAIT",wait); d.metric("SELL",sell)

    st.subheader("Market Results")
    for r in results:
        cls=r["Signal"].lower()
        st.markdown(f"""
        <div class="card">
        <b>{r["Stock"]}</b> &nbsp; ₹{r["LTP"]} &nbsp;
        {r["Change %"]:+.2f}% &nbsp; Trend: {r["Trend"]}<br>
        <span class="{cls}">{r["Signal"]}</span>
        &nbsp; Entry ₹{r["Entry"]} &nbsp; Target ₹{r["Target"]}
        &nbsp; Stop ₹{r["Stop Loss"]}
        </div>
        """,unsafe_allow_html=True)

    st.download_button("⬇️ Download CSV",
        pd.DataFrame(results).drop(columns="_score").to_csv(index=False),
        "swift_trade_scan.csv","text/csv",use_container_width=True)
else:
    st.info("Sector নির্বাচন করে SCAN MARKET চাপুন।")

st.caption("Swift Trade is a technical-analysis scanner. Signals are not guaranteed returns.")
    
