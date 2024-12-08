import ccxt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def fetch_ohlcv(exchange, symbol, timeframe, limit):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    # SMA
    df['sma_fast'] = df['close'].rolling(window=10).mean()
    df['sma_slow'] = df['close'].rolling(window=30).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = df['ema_12'] - df['ema_26']
    df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    return df

def get_signal(df):
    last_row = df.iloc[-1]
    
    # SMA Signal
    sma_signal = 1 if last_row['sma_fast'] > last_row['sma_slow'] else -1
    
    # RSI Signal
    rsi_signal = 0
    if last_row['rsi'] < 30:
        rsi_signal = 1  # Oversold
    elif last_row['rsi'] > 70:
        rsi_signal = -1  # Overbought
    
    # MACD Signal
    macd_signal = 1 if last_row['macd'] > last_row['signal_line'] else -1
    
    # Combine signals
    combined_signal = sma_signal + rsi_signal + macd_signal
    
    if combined_signal > 1:
        return "Strong Buy"
    elif combined_signal == 1:
        return "Buy"
    elif combined_signal == 0:
        return "Neutral"
    elif combined_signal == -1:
        return "Sell"
    else:
        return "Strong Sell"

def analyze_timeframes(exchange, symbol):
    timeframes = ['5m', '15m', '1h', '4h', '1d']
    results = {}
    
    for tf in timeframes:
        df = fetch_ohlcv(exchange, symbol, tf, limit=100)
        df = calculate_indicators(df)
        signal = get_signal(df)
        
        # Calculate trend score
        trend_score = abs(df['close'].pct_change(periods=10).mean()) * 100
        
        results[tf] = {
            'signal': signal,
            'trend_score': trend_score
        }
    
    return results

def suggest_trade_duration(signal, trend_score):
    if signal in ["Strong Buy", "Strong Sell"]:
        if trend_score > 1:
            return "4 hours"
        elif trend_score > 0.5:
            return "1 hour"
        else:
            return "30 minutes"
    elif signal in ["Buy", "Sell"]:
        if trend_score > 0.5:
            return "30 minutes"
        else:
            return "15 minutes"
    else:
        return "Wait for a clearer signal"

def main():
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })

    symbol = 'BTC/USDT'
    
    while True:
        try:
            print(f"Timestamp: {datetime.now()}")
            
            # Fetch current price
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            print(f"Current BTC Price: ${current_price:.2f}")
            
            # Analyze all timeframes
            results = analyze_timeframes(exchange, symbol)
            
            # Find the best timeframe
            best_tf = max(results, key=lambda x: abs(["Strong Sell", "Sell", "Neutral", "Buy", "Strong Buy"].index(results[x]['signal']) - 2))
            
            print("\nTimeframe Analysis:")
            for tf, data in results.items():
                print(f"{tf}: Signal - {data['signal']}, Trend Score - {data['trend_score']:.2f}%")
            
            print(f"\nBest Timeframe: {best_tf}")
            print(f"Recommended Signal: {results[best_tf]['signal']}")
            
            trade_duration = suggest_trade_duration(results[best_tf]['signal'], results[best_tf]['trend_score'])
            print(f"Suggested Trade Duration: {trade_duration}")
            
            print("-" * 50)
            
            # Wait for 1 minute before next analysis
            for i in range(60, 0, -1):
                print(f"Next analysis in {i} seconds...", end='\r')
                exchange.sleep(1000)  # Sleep for 1 second
            
        except Exception as e:
            print(f"An error occurred: {e}")
            exchange.sleep(60000)  # Sleep for 1 minute before retrying

if __name__ == "__main__":
    main()