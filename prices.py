import time

import yfinance as yf

from universe import get_sp500_symbols

# מורידים בקבוצות כדי לא להעמיס על yfinance
CHUNK_SIZE = 100


def get_latest_prices(symbols=None):
    """
    מחזיר שני דברים:
    1. מילון של המחיר האחרון הזמין לכל מניה
    2. השעה של הנתון האחרון, לפי שעון ישראל
    אם הבורסה סגורה, מקבלים את הנתון האחרון מיום המסחר האחרון.
    """
    if symbols is None:
        symbols = get_sp500_symbols()

    prices = {}
    last_time = None

    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            data = yf.download(chunk, period="1d", interval="1m",
                               progress=False, auto_adjust=True)
        except Exception as error:
            print("Failed to download a group of stocks:", error)
            continue
        if data.empty:
            continue

        closes = data["Close"]
        if not hasattr(closes, "columns"):  # כשיש מניה אחת בלבד
            closes = closes.to_frame(chunk[0])
        closes = closes.ffill()

        last_row = closes.iloc[-1]
        when = closes.index[-1].tz_convert("Asia/Jerusalem")
        if last_time is None or when > last_time:
            last_time = when

        for sym in chunk:
            price = last_row.get(sym)
            if price is not None and price == price:  # מדלג על ערכים חסרים
                prices[sym] = float(price)

    return prices, last_time


if __name__ == "__main__":
    # בדיקה קטנה, רצה רק כשמפעילים את הקובץ ישירות
    start = time.time()

    all_symbols = get_sp500_symbols()
    prices, when = get_latest_prices(all_symbols)
    print("Latest data time (Israel):", when)
    print("Stocks requested:", len(all_symbols), "| prices received:", len(prices))
    print("Seconds it took:", round(time.time() - start))
    for sym in list(prices)[:5]:
        print(f"  {sym}: ${prices[sym]:.2f}")