import requests
import pandas as pd
import time
from datetime import datetime

# ================== CONFIG ==================

TELEGRAM_BOT_TOKEN = "8408138871:AAEAFLXN-0_NX4f94DRTCfXAIY7IK5GDYmY"
TELEGRAM_CHAT_ID = "8565460915"

BASE_URL = "https://api.binance.com"
TIMEFRAME = "5m"
LIMIT = 100

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "LINKUSDT", "MATICUSDT"
]

# ================== TELEGRAM ==================

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    requests.post(url, data=data)

# ================== BINANCE ==================

def get_klines(symbol, interval, limit):
    url = f"{BASE_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        return None

    df = pd.DataFrame(r.json(), columns=[
        "time","open","high","low","close","volume",
        "c1","c2","c3","c4","c5","c6"
    ])

    df = df[["time","open","high","low","close","volume"]]
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df

# ================== INDICATORS ==================

def EMA(series, period):
    return series.ewm(span=period, adjust=False).mean()

def RSI(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================== BTC FILTER (LOOSE) ==================

def btc_market_ok():
    df = get_klines("BTCUSDT", "15m", 100)
    if df is None or len(df) < 50:
        return False

    ema50 = EMA(df["close"], 50).iloc[-1]
    price = df["close"].iloc[-1]

    return price >= ema50 * 0.995  # loose institutional filter

# ================== SCORE LOGIC ==================

def calculate_score(df):
    score = 0
    reasons = []

    ema9 = EMA(df["close"], 9)
    ema21 = EMA(df["close"], 21)
    ema50 = EMA(df["close"], 50)

    rsi = RSI(df["close"])
    vol_avg = df["volume"].rolling(20).mean()

    if ema9.iloc[-1] > ema21.iloc[-1]:
        score += 1
        reasons.append("EMA9 > EMA21")

    if ema21.iloc[-1] > ema50.iloc[-1]:
        score += 1
        reasons.append("EMA21 > EMA50")

    if 45 <= rsi.iloc[-1] <= 70:
        score += 1
        reasons.append("RSI healthy")

    if df["volume"].iloc[-1] > vol_avg.iloc[-1]:
        score += 1
        reasons.append("Volume spike")

    if btc_market_ok():
        score += 1
        reasons.append("BTC trend OK")

    return score, reasons

# ================== MAIN SCAN ==================

def run_once():
    send_telegram("🔁 Scan Started – Checking Market")

    if not btc_market_ok():
        send_telegram("⚠️ BTC weak/neutral – signals limited")

    for symbol in SYMBOLS:
        df = get_klines(symbol, TIMEFRAME, LIMIT)
        if df is None or len(df) < 50:
            continue

        score, reasons = calculate_score(df)

        if score >= 3:
            price = df["close"].iloc[-1]
            msg = (
                f"🚀 SPOT SIGNAL\n\n"
                f"🪙 Coin: {symbol}\n"
                f"⏱ TF: {TIMEFRAME}\n"
                f"💰 Price: {price}\n"
                f"⭐ Score: {score}/5\n\n"
                f"🧠 Reasons:\n- " + "\n- ".join(reasons) +
                f"\n\n⏰ {datetime.utcnow()} UTC"
            )
            send_telegram(msg)

# ================== ENTRY ==================

if __name__ == "__main__":
    send_telegram("🚀 Crypto Spot Institutional Engine STARTED")
    run_once()
