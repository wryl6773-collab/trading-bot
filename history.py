import time

import pandas as pd
import yfinance as yf

from universe import get_sp500_symbols

# מורידים בקבוצות כדי לא להעמיס על yfinance
CHUNK_SIZE = 100
FIELDS = ["Close", "High", "Low", "Volume"]


def get_daily_history(symbols=None, period="1y"):
    """
    מוריד היסטוריית מחירים יומית. מחזיר מילון של טבלאות:
    לכל שדה (Close, High, Low, Volume) יש טבלה,
    שבה כל עמודה היא מניה וכל שורה היא יום מסחר.
    """
    if symbols is None:
        symbols = get_sp500_symbols()

    parts = {field: [] for field in FIELDS}
    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i:i + CHUNK_SIZE]
        try:
            data = yf.download(chunk, period=period, interval="1d",
                               progress=False, auto_adjust=True)
        except Exception as error:
            print("Failed to download a group of stocks:", error)
            continue
        if data.empty:
            continue
        for field in FIELDS:
            table = data[field]
            if not hasattr(table, "columns"):  # כשיש מניה אחת בלבד
                table = table.to_frame(chunk[0])
            parts[field].append(table)

    history = {}
    for field in FIELDS:
        if parts[field]:
            history[field] = pd.concat(parts[field], axis=1)
    return history


if __name__ == "__main__":
    # בדיקה קטנה, רצה רק כשמפעילים את הקובץ ישירות
    start = time.time()
    history = get_daily_history()
    close = history["Close"]
    print("Days:", len(close), "| stocks:", close.shape[1])
    print("First day:", close.index[0].date(), "| last day:", close.index[-1].date())
    print("Seconds it took:", round(time.time() - start))
    print("AAPL last close:", round(float(close["AAPL"].iloc[-1]), 2))