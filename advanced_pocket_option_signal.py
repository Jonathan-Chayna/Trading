import ccxt
import numpy as np
import pandas as pd
from datetime import datetime
import talib

def fetch_ohlcv(exchange, symbol, timeframe, limit):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    # Strategy 1: SMA, RSI, MACD
    df['sma_fast'] = talib.SMA(df['close'], timeperiod=10)
    df['sma_slow'] = talib.SMA(df['close'], timeperiod=30)
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['macd'], df['macdsignal'], _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
    
    # Strategy 2: Bollinger Bands, Stochastic Oscillator, ADX
    df['upper'], df['middle'], df['lower'] = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    df['slowk'], df['slowd'] = talib.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
    df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
    
    # Strategy 3: Dynamic Blue ZigZag Lines
    df = calculate_pivot_points(df)
    
    return df

def calculate_pivot_points(df, length=10):
    df['swing_high'] = df['high'].rolling(window=length*2+1, center=True).max()
    df['swing_low'] = df['low'].rolling(window=length*2+1, center=True).min()
    df['is_pivot_high'] = (df['swing_high'] == df['high']) & (df['swing_high'].shift(length) != df['swing_high'])
    df['is_pivot_low'] = (df['swing_low'] == df['low']) & (df['swing_low'].shift(length) != df['swing_low'])
    return df

def get_signal_strategy1(df):
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
    macd_signal = 1 if last_row['macd'] > last_row['macdsignal'] else -1
    
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

def get_signal_strategy2(df):
    last_row = df.iloc[-1]
    
    # Bollinger Bands Signal
    bb_signal = 0
    if last_row['close'] < last_row['lower']:
        bb_signal = 1  # Oversold
    elif last_row['close'] > last_row['upper']:
        bb_signal = -1  # Overbought
    
    # Stochastic Oscillator Signal
    stoch_signal = 0
    if last_row['slowk'] < 20 and last_row['slowd'] < 20:
        stoch_signal = 1  # Oversold
    elif last_row['slowk'] > 80 and last_row['slowd'] > 80:
        stoch_signal = -1  # Overbought
    
    # ADX Signal
    adx_signal = 1 if last_row['adx'] > 25 else 0  # Strong trend if ADX > 25
    
    # Combine signals
    combined_signal = bb_signal + stoch_signal + adx_signal
    
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

def get_signal_strategy3(df):
    last_pivot_high = df[df['is_pivot_high']].iloc[-1] if not df[df['is_pivot_high']].empty else None
    last_pivot_low = df[df['is_pivot_low']].iloc[-1] if not df[df['is_pivot_low']].empty else None
    current_price = df['close'].iloc[-1]
    
    if last_pivot_high is not None and last_pivot_low is not None:
        if last_pivot_high.name > last_pivot_low.name:  # Last pivot was a high
            if current_price < last_pivot_high['high']:
                return "Sell"
            else:
                return "Buy"
        else:  # Last pivot was a low
            if current_price > last_pivot_low['low']:
                return "Buy"
            else:
                return "Sell"
    
    return "Neutral"

def analyze_timeframes(exchange, symbol):
    timeframes = ['1m', '5m', '15m', '30m', '1h']
    results = {}
    
    for tf in timeframes:
        df = fetch_ohlcv(exchange, symbol, tf, limit=100)
        df = calculate_indicators(df)
        signal1 = get_signal_strategy1(df)
        signal2 = get_signal_strategy2(df)
        signal3 = get_signal_strategy3(df)
        
        # Calculate trend score
        trend_score = abs(df['close'].pct_change(periods=5).mean()) * 100
        
        results[tf] = {
            'signal1': signal1,
            'signal2': signal2,
            'signal3': signal3,
            'trend_score': trend_score
        }
    
    return results

def suggest_trade_duration(signal, trend_score):
    if signal in ["Strong Buy", "Strong Sell"]:
        if trend_score > 0.5:
            return "5 minutes"
        elif trend_score > 0.2:
            return "3 minutes"
        else:
            return "1 minute"
    elif signal in ["Buy", "Sell"]:
        if trend_score > 0.2:
            return "2 minutes"
        else:
            return "1 minute"
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
            
            # Find the best timeframe for each strategy
            best_tf1 = max(results, key=lambda x: abs(["Strong Sell", "Sell", "Neutral", "Buy", "Strong Buy"].index(results[x]['signal1']) - 2))
            best_tf2 = max(results, key=lambda x: abs(["Strong Sell", "Sell", "Neutral", "Buy", "Strong Buy"].index(results[x]['signal2']) - 2))
            best_tf3 = max(results, key=lambda x: abs(["Sell", "Neutral", "Buy"].index(results[x]['signal3']) - 1))
            
            print("\nTimeframe Analysis:")
            for tf, data in results.items():
                print(f"{tf}: Strategy 1 - {data['signal1']}, Strategy 2 - {data['signal2']}, Strategy 3 - {data['signal3']}, Trend Score - {data['trend_score']:.2f}%")
            
            print(f"\nStrategy 1 (SMA, RSI, MACD):")
            print(f"Best Timeframe: {best_tf1}")
            print(f"Recommended Signal: {results[best_tf1]['signal1']}")
            trade_duration1 = suggest_trade_duration(results[best_tf1]['signal1'], results[best_tf1]['trend_score'])
            print(f"Suggested Trade Duration: {trade_duration1}")
            
            print(f"\nStrategy 2 (Bollinger Bands, Stochastic, ADX):")
            print(f"Best Timeframe: {best_tf2}")
            print(f"Recommended Signal: {results[best_tf2]['signal2']}")
            trade_duration2 = suggest_trade_duration(results[best_tf2]['signal2'], results[best_tf2]['trend_score'])
            print(f"Suggested Trade Duration: {trade_duration2}")
            
            print(f"\nStrategy 3 (Dynamic Blue ZigZag Lines):")
            print(f"Best Timeframe: {best_tf3}")
            print(f"Recommended Signal: {results[best_tf3]['signal3']}")
            trade_duration3 = suggest_trade_duration(results[best_tf3]['signal3'], results[best_tf3]['trend_score'])
            print(f"Suggested Trade Duration: {trade_duration3}")
            
            print("-" * 50)
            
            # Wait for 30 seconds before next analysis
            for i in range(30, 0, -1):
                print(f"Next analysis in {i} seconds...", end='\r')
                exchange.sleep(1000)  # Sleep for 1 second
            
        except Exception as e:
            print(f"An error occurred: {e}")
            exchange.sleep(30000)  # Sleep for 30 seconds before retrying

if __name__ == "__main__":
    main()

