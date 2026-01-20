import requests
import pandas as pd
import time

# ================= TELEGRAM CONFIG =================
BOT_TOKEN = "8408138871:AAEAFLXN-0_NX4f94DRTCfXAIY7IK5GDYmY"
CHAT_ID = "8565460915"

# ================= TELEGRAM SEND =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data, timeout=10)
    except:
        pass

# ================= EMA & RSI =================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================= OHLC =================
def get_ohlc(symbol, interval, limit=200):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            return pd.DataFrame()

        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume",
            "x1","x2","x3","x4","x5","x6"
        ])

        df[["open","high","low","close","volume"]] = df[
            ["open","high","low","close","volume"]
        ].astype(float)

        return df
    except:
        return pd.DataFrame()

# ================= INDICATORS =================
def add_indicators(df):
    if df.empty or len(df) < 100:
        return pd.DataFrame()

    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"], 14)
    return df

# ================= BTC MASTER FILTER =================
def btc_market_ok():
    df = add_indicators(get_ohlc("BTCUSDT", "15m"))
    if df.empty:
        return False

    score = 0
    if df["close"].iloc[-1] > df["ema200"].iloc[-1]:
        score += 1
    if df["rsi"].iloc[-1] > 45:
        score += 1
    if df["ema20"].iloc[-1] > df["ema50"].iloc[-1]:
        score += 1

    return score >= 2

# ================= BACKTEST =================
def backtest(symbol):
    df = add_indicators(get_ohlc(symbol, "1m", 500))
    if df.empty:
        return None

    wins = 0
    losses = 0

    for i in range(200, len(df)-10):
        score = 0

        if df["ema20"].iloc[i] > df["ema50"].iloc[i]:
            score += 1
        if 40 <= df["rsi"].iloc[i] <= 60:
            score += 1
        if df["close"].iloc[i] > df["ema20"].iloc[i]:
            score += 1
        if df["volume"].iloc[i] > df["volume"].iloc[i-1]:
            score += 1

        if score >= 4:
            entry = df["close"].iloc[i]
            tp = entry * 1.005
            sl = entry * 0.997
            future = df.iloc[i+1:i+10]

            if future["high"].max() >= tp:
                wins += 1
            elif future["low"].min() <= sl:
                losses += 1

    total = wins + losses
    if total == 0:
        return None

    return round((wins / total) * 100, 2)

# ================= TOP COINS =================
def get_top_coins():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        data = requests.get(url, timeout=10).json()
        df = pd.DataFrame(data)
        df = df[df["symbol"].str.endswith("USDT")]
        df["quoteVolume"] = pd.to_numeric(df["quoteVolume"], errors="coerce")
        return df.sort_values("quoteVolume", ascending=False).head(30)["symbol"].tolist()
    except:
        return []

# ================= ANALYZE =================
def analyze_coin(symbol):
    df1 = add_indicators(get_ohlc(symbol, "1m"))
    df5 = add_indicators(get_ohlc(symbol, "5m"))
    df15 = add_indicators(get_ohlc(symbol, "15m"))

    if df1.empty or df5.empty or df15.empty:
        return None

    score = 0
    reasons = []

    if df15["ema20"].iloc[-1] > df15["ema50"].iloc[-1]:
        score += 1; reasons.append("EMA Bullish 15m")
    if df5["ema20"].iloc[-1] > df5["ema50"].iloc[-1]:
        score += 1; reasons.append("EMA Bullish 5m")
    if 40 <= df5["rsi"].iloc[-1] <= 60:
        score += 1; reasons.append("RSI Healthy")
    if df1["volume"].iloc[-1] > df1["volume"].iloc[-2]:
        score += 1; reasons.append("Volume Spike")
    if df1["close"].iloc[-1] > df1["ema20"].iloc[-1]:
        score += 1; reasons.append("Price Above EMA20")

    return score, reasons, df1["close"].iloc[-1]

# ================= ENGINE =================
def run_engine():
    send_telegram("🚀 Crypto Spot Institutional Engine STARTED")

    while True:
        try:
            if not btc_market_ok():
                time.sleep(300)
                continue

            for coin in get_top_coins():
                result = analyze_coin(coin)
                if not result:
                    continue

                score, reasons, price = result
                if score < 4:
                    continue

                winrate = backtest(coin)
                if winrate is None or winrate < 55:
                    continue

                msg = (
                    f"🟢 BUY SIGNAL (SPOT)\n\n"
                    f"COIN: {coin}\n"
                    f"PRICE: {price:.4f}\n"
                    f"SCORE: {score}/5\n"
                    f"WIN RATE: {winrate}%\n\n"
                    f"CONFIRMATIONS:\n- " + "\n- ".join(reasons)
                )

                send_telegram(msg)
                time.sleep(10)

            time.sleep(300)

        except Exception as e:
            send_telegram(f"⚠️ Engine Error: {e}")
            time.sleep(60)

# ================= START =================
run_engine()
