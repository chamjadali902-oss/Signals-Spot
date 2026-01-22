import requests
import pandas as pd
from datetime import datetime
import traceback

# ================= CONFIG =================

TELEGRAM_BOT_TOKEN = "8408138871:AAEAFLXN-0_NX4f94DRTCfXAIY7IK5GDYmY"
TELEGRAM_CHAT_ID = "8565460915"

BASE_URL = "https://api.binance.com"
TIMEFRAME = "5m"
LIMIT = 120
TOP_LIMIT = 100

# ================= TELEGRAM =================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

# ================= BINANCE =================

def safe_float(x):
    try:
        return float(x)
    except:
        return None

def get_klines(symbol, interval, limit):
    try:
        r = requests.get(
            f"{BASE_URL}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10
        )
        if r.status_code != 200:
            return None

        df = pd.DataFrame(r.json(), columns=[
            "t","o","h","l","c","v","_","_","_","_","_","_"
        ])
        df = df[["o","h","l","c","v"]].astype(float)
        df.columns = ["open","high","low","close","volume"]
        return df
    except:
        return None

def get_24h_tickers():
    try:
        r = requests.get(f"{BASE_URL}/api/v3/ticker/24hr", timeout=10)
        if r.status_code != 200:
            return []
        return r.json()
    except:
        return []

# ================= INDICATORS =================

def EMA(s, p):
    return s.ewm(span=p, adjust=False).mean()

def RSI(s, p=14):
    d = s.diff()
    g = d.clip(lower=0)
    l = -d.clip(upper=0)
    ag = g.rolling(p).mean()
    al = l.rolling(p).mean()
    rs = ag / al
    return 100 - (100 / (1 + rs))

# ================= BTC SAFETY =================

def btc_safe():
    df = get_klines("BTCUSDT", "15m", 100)
    if df is None or len(df) < 50:
        return False
    ema100 = EMA(df["close"], 100).iloc[-1]
    price = df["close"].iloc[-1]
    return price >= ema100 * 0.99

# ================= STRATEGIES =================

def trend_score(df):
    score, reasons = 0, []
    ema9 = EMA(df["close"], 9)
    ema21 = EMA(df["close"], 21)
    ema50 = EMA(df["close"], 50)
    rsi = RSI(df["close"])
    vol_avg = df["volume"].rolling(20).mean()

    if ema9.iloc[-1] > ema21.iloc[-1]:
        score += 1; reasons.append("EMA9>EMA21")
    if ema21.iloc[-1] > ema50.iloc[-1]:
        score += 1; reasons.append("EMA21>EMA50")
    if 45 <= rsi.iloc[-1] <= 70:
        score += 1; reasons.append("RSI healthy")
    if df["volume"].iloc[-1] > vol_avg.iloc[-1]:
        score += 1; reasons.append("Volume spike")
    if btc_safe():
        score += 1; reasons.append("BTC safe")

    return score, reasons

def reversal_score(df):
    score, reasons = 0, []
    ema9 = EMA(df["close"], 9)
    ema21 = EMA(df["close"], 21)
    rsi = RSI(df["close"])
    vol_avg = df["volume"].rolling(20).mean()

    if rsi.iloc[-2] < 35 and rsi.iloc[-1] > rsi.iloc[-2]:
        score += 1; reasons.append("RSI bounce")
    if ema9.iloc[-1] > ema21.iloc[-1] and ema9.iloc[-2] <= ema21.iloc[-2]:
        score += 1; reasons.append("EMA cross")
    if df["volume"].iloc[-1] > vol_avg.iloc[-1]:
        score += 1; reasons.append("Volume spike")
    if df["close"].iloc[-1] > df["close"].iloc[-2]:
        score += 1; reasons.append("Green candle")

    return score, reasons

# ================= MAIN =================

def run_once():
    send_telegram("🔁 Dual Strategy1 Scan Running")

    tickers = get_24h_tickers()

    # -------- TOP 100 VOLUME (CONTINUATION) --------
    volume_coins = sorted(
        [c for c in tickers if c.get("symbol","").endswith("USDT") and safe_float(c.get("quoteVolume"))],
        key=lambda x: safe_float(x["quoteVolume"]),
        reverse=True
    )[:TOP_LIMIT]

    for c in volume_coins:
        try:
            df = get_klines(c["symbol"], TIMEFRAME, LIMIT)
            if df is None:
                continue
            score, reasons = trend_score(df)
            if score >= 3:
                send_telegram(
                    f"📈 CONTINUATION\n{c['symbol']}\nScore: {score}/5\n" +
                    " | ".join(reasons)
                )
        except:
            continue

    # -------- TOP 100 LOSERS (REVERSAL) --------
    losers = sorted(
        [c for c in tickers if c.get("symbol","").endswith("USDT") and safe_float(c.get("priceChangePercent"))],
        key=lambda x: safe_float(x["priceChangePercent"])
    )[:TOP_LIMIT]

    for c in losers:
        try:
            df = get_klines(c["symbol"], TIMEFRAME, LIMIT)
            if df is None:
                continue
            score, reasons = reversal_score(df)
            if score >= 3:
                send_telegram(
                    f"🔄 REVERSAL\n{c['symbol']}\n24h: {c['priceChangePercent']}%\n" +
                    " | ".join(reasons)
                )
        except:
            continue

# ================= ENTRY =================

if __name__ == "__main__":
    try:
        send_telegram("🚀 Engine Started Successfully")
        run_once()
    except Exception as e:
        send_telegram("❌ BOT CRASHED:\n" + str(e))
        send_telegram(traceback.format_exc())
