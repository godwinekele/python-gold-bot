import MetaTrader5 as mt5
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText

# ------------------ SETTINGS ------------------
SYMBOL = "XAUUSDm"
LOT = 0.01

EMA_FAST = 5
EMA_SLOW = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 60
RSI_OVERSOLD = 40

SL_POINTS = 1000          # $1 SL
TP_POINTS = 2000          # $2 TP (trigger only)

BREAK_EVEN_TRIGGER = 2.0  # $2
TRAIL_STEP = 1.0          # $1 steps

CHECK_EVERY_SEC = 60
MAX_TRADE_MINUTES = 10

# HTF = mt5.TIMEFRAME_M5
#MAGIC = 777001

# Email settings (UNCHANGED)
EMAIL_FROM = "godwinekele19@gmail.com"
EMAIL_TO = "godwinekele19@gmail.com"
EMAIL_APP_PASSWORD = "qiyrowmyjqulmiqy"
# ---------------------------------------------

if not mt5.initialize():
    print("MT5 failed to start")
    quit()

print("Bot started and connected")

# ------------------ EMAIL ------------------
def send_email(subject, body):
    msg = MIMEText(body)
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.send_message(msg)

# ------------------ DATA ------------------
def get_data(symbol, timeframe, n=100):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    df = pd.DataFrame(rates)
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(RSI_PERIOD).mean() / loss.rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100 / (1 + rs))
    return df

# ------------------ HTF TREND ------------------
def htf_trend(symbol):
    df = get_data(symbol, HTF, 50)
    return "BUY" if df.ema_fast.iloc[-1] > df.ema_slow.iloc[-1] else "SELL"

# ------------------ SIGNAL ------------------
def trade_signal(df):
    last, prev = df.iloc[-1], df.iloc[-2]
    trend = htf_trend(SYMBOL)

    if (
        prev.ema_fast < prev.ema_slow
        and last.ema_fast > last.ema_slow
        and last.rsi < RSI_OVERBOUGHT
        and trend == "BUY"
    ):
        return "BUY"

    if (
        prev.ema_fast > prev.ema_slow
        and last.ema_fast < last.ema_slow
        and last.rsi > RSI_OVERSOLD
        and trend == "SELL"
    ):
        return "SELL"

    return None

# ------------------ ORDER ------------------
def place_order(signal):
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions:
        return  # prevent stacking

    tick = mt5.symbol_info_tick(SYMBOL)
    price = tick.ask if signal == "BUY" else tick.bid

    sl = price - SL_POINTS / 1000 if signal == "BUY" else price + SL_POINTS / 1000
    tp = price + TP_POINTS / 1000 if signal == "BUY" else price - TP_POINTS / 1000

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC,
        "comment": "Scalper",
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        msg = f"Position opened: {signal} at {price}"
        print(msg)
        send_email(f"{SYMBOL} Trade Opened", msg)

# ------------------ MANAGEMENT ------------------
def manage_trades():
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return

    tick = mt5.symbol_info_tick(SYMBOL)

    for pos in positions:
        price = tick.bid if pos.type == 0 else tick.ask
        open_minutes = (time.time() - pos.time) / 60

        # Time-based exit
        if open_minutes >= MAX_TRADE_MINUTES and pos.profit <= 0:
            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": SYMBOL,
                "volume": pos.volume,
                "type": close_type,
                "price": price,
                "deviation": 20,
                "magic": MAGIC,
            })
            msg = "Trade closed due to timeout"
            print(msg)
            send_email(f"{SYMBOL} Trade Timeout", msg)
            continue

        # TP → Break-even
        if pos.tp != 0:
            hit_tp = price >= pos.tp if pos.type == 0 else price <= pos.tp
            if hit_tp:
                mt5.order_send({
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "sl": pos.price_open,
                    "tp": 0,
                })
                msg = "TP reached → Break-even activated"
                print(msg)
                send_email(f"{SYMBOL} Break-even", msg)

        # Trailing profit
        if pos.profit >= BREAK_EVEN_TRIGGER:
            steps = int((pos.profit - BREAK_EVEN_TRIGGER) // TRAIL_STEP)
            lock = BREAK_EVEN_TRIGGER + steps * TRAIL_STEP

            if pos.type == 0:
                new_sl = pos.price_open + lock / 10
                if pos.sl < new_sl:
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "sl": new_sl,
                        "tp": 0,
                    })
            else:
                new_sl = pos.price_open - lock / 10
                if pos.sl > new_sl or pos.sl == 0:
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "sl": new_sl,
                        "tp": 0,
                    })

# ------------------ MAIN LOOP ------------------
while True:
    df = get_data(SYMBOL, mt5.TIMEFRAME_M1)
    signal = trade_signal(df)
    if signal:
        place_order(signal)

    manage_trades()
    time.sleep(CHECK_EVERY_SEC)
