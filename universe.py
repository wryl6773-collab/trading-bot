import io
import json
import os

import pandas as pd
import requests

from portfolio import DATA_DIR

SP500_CACHE = os.path.join(DATA_DIR, "sp500.json")
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _download_sp500():
    """מוריד את רשימת חברות ה-S&P 500 מוויקיפדיה."""
    headers = {"User-Agent": "Mozilla/5.0 (paper trading bot, learning project)"}
    response = requests.get(WIKI_URL, headers=headers, timeout=30)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    symbols = tables[0]["Symbol"].tolist()
    # yfinance כותב נקודה כמקף, למשל BRK.B הופך ל-BRK-B
    return [s.replace(".", "-") for s in symbols]


def get_sp500_symbols():
    """מחזיר רשימת סימולים. אם ההורדה נכשלת, משתמש בעותק השמור."""
    try:
        symbols = _download_sp500()
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SP500_CACHE, "w", encoding="utf-8") as f:
            json.dump(symbols, f)
        return symbols
    except Exception as error:
        if os.path.exists(SP500_CACHE):
            print("Could not download the list, using the saved copy:", error)
            with open(SP500_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        raise


if __name__ == "__main__":
    # בדיקה קטנה, רצה רק כשמפעילים את הקובץ ישירות
    symbols = get_sp500_symbols()
    print("Number of stocks:", len(symbols))
    print("First 10:", symbols[:10])