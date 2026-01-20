import requests
import pandas as pd

BOT_TOKEN = "8408138871:AAEAFLXN-0_NX4f94DRTCfXAIY7IK5GDYmY"
CHAT_ID = "8565460915"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=data)

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

def get_ohlc(symbol, interval, limit=200):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not isinstance(data, list):
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

def add_indicators(df):
    if df.empty or len(df) < 100:
        return pd.DataFrame()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"], 14)
    return df

def btc_market_ok():
    df = add_indicators(get_ohlc("BTCUSDT", "15m"))
    if df.empty:
        return False
    score = 0
    if df["close"].iloc[-1] > df["ema200"].iloc[-1]: score += 1
    if df["rsi"].iloc[-1] > 45: score += 1
    if df["ema20"].iloc[-1] > df["ema50"].iloc[-1]: score += 1
    return score >= 2

def backtest(symbol):
    df = add_indicators(get_ohlc(symbol, "1m", 500))
    if df.empty:
        return None
    wins = losses = 0
    for i in range(200, len(df)-10):
        score = 0
        if df["ema20"].iloc[i] > df["ema50"].iloc[i]: score += 1
        if 40 <= df["rsi"].iloc[i] <= 60: score += 1
        if df["close"].iloc[i] > df["ema20"].iloc[i]: score += 1
        if df["volume"].iloc[i] > df["volume"].iloc[i-1]: score += 1
        if score >= 4:
            entry = df["close"].iloc[i]
            tp = entry * 1.005
            sl = entry * 0.997
            future = df.iloc[i+1:i+10]
            if future["high"].max() >= tp: wins += 1
            elif future["low"].min() <= sl: losses += 1
    total = wins + losses
    if total == 0:
        return None
    return round((wins / total) * 100, 2)

def get_top_coins():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    df = pd.DataFrame(requests.get(url).json())
    df = df[df["symbol"].str.endswith("USDT")]
    df["quoteVolume"] = pd.to_numeric(df["quoteVolume"], errors="coerce")
    return df.sort_values("quoteVolume", ascending=False).head(25)["symbol"].tolist()

def run_once():
    if not btc_market_ok():
        return

    for coin in get_top_coins():
        df1 = add_indicators(get_ohlc(coin, "1m"))
        df5 = add_indicators(get_ohlc(coin, "5m"))
        df15 = add_indicators(get_ohlc(coin, "15m"))
        if df1.empty or df5.empty or df15.empty:
            continue

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

        if score >= 4:
            winrate = backtest(coin)
            if winrate and winrate >= 55:
                price = df1["close"].iloc[-1]
                send_telegram(
                    f"🟢 BUY SIGNAL (SPOT)\n\n"
                    f"COIN: {coin}\n"
                    f"PRICE: {price:.4f}\n"
                    f"SCORE: {score}/5\n"
                    f"WIN RATE: {winrate}%\n\n"
                    f"- " + "\n- ".join(reasons)
                )

run_once()
