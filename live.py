import yfinance as yf

from universe import get_sp500_symbols

CHUNK_SIZE = 100


def get_live_snapshot(symbols=None):
    """
    מחזיר את המצב של היום עד הרגע הזה, לכל מניה:
    1. המחיר האחרון  2. נפח המסחר המצטבר מתחילת היום  3. השעה של הנתון האחרון.
    """
    if symbols is None:
        symbols = get_sp500_symbols()

    prices, volumes, last_time = {}, {}, None
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

        closes, vols = data["Close"], data["Volume"]
        if not hasattr(closes, "columns"):  # כשיש מניה אחת בלבד
            closes = closes.to_frame(chunk[0])
            vols = vols.to_frame(chunk[0])
        closes = closes.ffill()
        last_row = closes.iloc[-1]
        total_vol = vols.fillna(0).sum()

        when = closes.index[-1]
        if last_time is None or when > last_time:
            last_time = when

        for sym in chunk:
            p = last_row.get(sym)
            if p is not None and p == p:
                prices[sym] = float(p)
                volumes[sym] = float(total_vol.get(sym, 0.0))
    return prices, volumes, last_time
