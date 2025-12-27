import MetaTrader5 as mt5
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ------------------ SETTINGS ------------------
SYMBOL = "XAUUSDm"
LOT = 0.01
EMA_FAST = 5
EMA_SLOW = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 60
RSI_OVERSOLD = 40
SL_POINTS = 1000  # $1 SL
TP_POINTS = 2000  # $2 TP (trigger only)
BREAK_EVEN_TRIGGER = 2.0  # $2
TRAIL_STEP = 1.0  # $1 steps
CHECK_EVERY_SEC = 60
MAX_TRADE_MINUTES = 10

# FIXED: Define HTF and MAGIC
HTF = mt5.TIMEFRAME_M5
MAGIC = 777001

# Email settings
EMAIL_FROM = os.getenv("EMAIL_FROM", "godwinekele19@gmail.com")
EMAIL_TO = os.getenv("EMAIL_TO", "godwinekele19@gmail.com")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "qiyrowmyjqulmiqy")

# MT5 connection settings
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

# --------------------------------------------- 

if not mt5.initialize():
    print("MT5 failed to start")
    quit()

# Login to MT5 account (required for Docker/Wine setup)
if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
    authorized = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not authorized:
        print(f"Failed to login to MT5 account #{MT5_LOGIN}")
        print(f"Error: {mt5.last_error()}")
        quit()
    print(f"Connected to MT5 account #{MT5_LOGIN}")
else:
    print("Warning: MT5 credentials not provided. Using existing connection.")

print("Bot started and connected")

# ------------------ EMAIL ------------------
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO
        msg["Subject"] = subject
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email error: {e}")

# ------------------ DATA ------------------
def get_data(symbol, timeframe, n=100):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    if rates is None or len(rates) == 0:
        print(f"Failed to get data for {symbol}")
        return None
    
    df = pd.DataFrame(rates)
    df["ema_fast"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.rolling(RSI_PERIOD).mean()
    avg_loss = loss.rolling(RSI_PERIOD).mean()
    
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    return df

# ------------------ HTF TREND ------------------
def htf_trend(symbol):
    df = get_data(symbol, HTF, 50)
    if df is None:
        return None
    return "BUY" if df.ema_fast.iloc[-1] > df.ema_slow.iloc[-1] else "SELL"

# ------------------ SIGNAL ------------------
def trade_signal(df):
    if df is None or len(df) < 2:
        return None
    
    last, prev = df.iloc[-1], df.iloc[-2]
    trend = htf_trend(SYMBOL)
    
    if trend is None:
        return None
    
    # Buy signal
    if (prev.ema_fast < prev.ema_slow and 
        last.ema_fast > last.ema_slow and 
        last.rsi < RSI_OVERBOUGHT and 
        trend == "BUY"):
        return "BUY"
    
    # Sell signal
    if (prev.ema_fast > prev.ema_slow and 
        last.ema_fast < last.ema_slow and 
        last.rsi > RSI_OVERSOLD and 
        trend == "SELL"):
        return "SELL"
    
    return None

# ------------------ ORDER ------------------
def place_order(signal):
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions:
        print("Position already open, skipping...")
        return
    
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        print(f"Failed to get tick for {SYMBOL}")
        return
    
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
    else:
        print(f"Order failed: {result.retcode} - {result.comment}")

# ------------------ MANAGEMENT ------------------
def manage_trades():
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        return
    
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        return
    
    for pos in positions:
        price = tick.bid if pos.type == 0 else tick.ask
        open_minutes = (time.time() - pos.time) / 60
        
        # Time-based exit
        if open_minutes >= MAX_TRADE_MINUTES and pos.profit <= 0:
            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": SYMBOL,
                "volume": pos.volume,
                "type": close_type,
                "price": price,
                "deviation": 20,
                "magic": MAGIC,
            }
            result = mt5.order_send(close_request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                msg = "Trade closed due to timeout"
                print(msg)
                send_email(f"{SYMBOL} Trade Timeout", msg)
            continue
        
        # TP → Break-even
        if pos.tp != 0:
            hit_tp = price >= pos.tp if pos.type == 0 else price <= pos.tp
            if hit_tp:
                sltp_request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "sl": pos.price_open,
                    "tp": 0,
                }
                result = mt5.order_send(sltp_request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    msg = "TP reached → Break-even activated"
                    print(msg)
                    send_email(f"{SYMBOL} Break-even", msg)
        
        # Trailing profit
        if pos.profit >= BREAK_EVEN_TRIGGER:
            steps = int((pos.profit - BREAK_EVEN_TRIGGER) // TRAIL_STEP)
            lock = BREAK_EVEN_TRIGGER + steps * TRAIL_STEP
            
            if pos.type == 0:  # Buy position
                new_sl = pos.price_open + lock / 10
                if pos.sl < new_sl:
                    sltp_request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "sl": new_sl,
                        "tp": 0,
                    }
                    mt5.order_send(sltp_request)
            else:  # Sell position
                new_sl = pos.price_open - lock / 10
                if pos.sl > new_sl or pos.sl == 0:
                    sltp_request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "sl": new_sl,
                        "tp": 0,
                    }
                    mt5.order_send(sltp_request)

# ------------------ MAIN LOOP ------------------
if __name__ == "__main__":
    print("Starting main trading loop...")
    while True:
        try:
            df = get_data(SYMBOL, mt5.TIMEFRAME_M1)
            if df is not None:
                signal = trade_signal(df)
                if signal:
                    place_order(signal)
                
                manage_trades()
            
            time.sleep(CHECK_EVERY_SEC)
        
        except KeyboardInterrupt:
            print("\nBot stopped by user")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(CHECK_EVERY_SEC)
    
    mt5.shutdown()
    print("MT5 connection closed")
