import importlib

from portfolio import Account

START_CASH_USD = 550.0   # הון התחלתי לכל אסטרטגיה, בדולרים
BUY_FRACTION = 0.10      # כל קנייה היא 10% מההון ההתחלתי (אלא אם האסטרטגיה ביקשה אחרת)
FEE_RATE = 0.001         # עמלה מדומה: 0.1% מגודל העסקה

# האסטרטגיות שהמנוע מריץ. נוסיף לכאן עוד כשנבנה אותן.
STRATEGY_MODULES = [
    "strategy_moving_average",
    "strategy_momentum",
    "strategy_mean_reversion",
    "strategy_rsi",
    "strategy_macd",
    "strategy_breakout",
    "strategy_trailing_stop",
    "strategy_volume",
    "strategy_dca",
    "strategy_buy_and_hold",
]


def run_strategies(close, now_str, accounts, volume=None):
    """
    מריץ את כל האסטרטגיות על מחירי הסגירה ומבצע את ההחלטות שלהן
    בחשבונות הווירטואליים. close ו-volume הם טבלאות עד הרגע הנוכחי בלבד.
    volume (נפח מסחר) נדרש רק לאסטרטגיות שמצהירות NEEDS_VOLUME = True.
    """
    prices = close.iloc[-1]  # המחיר האחרון הידוע לכל מניה

    for module_name in STRATEGY_MODULES:
        strategy = importlib.import_module(module_name)
        name = strategy.STRATEGY_NAME

        if name not in accounts:
            accounts[name] = Account(name, START_CASH_USD)
        account = accounts[name]

        # אסטרטגיה שמוגדרת ONCE_PER_DAY פועלת פעם אחת בלבד בכל יום מסחר
        # (אפשר גם פונקציה שמחליטה לפי הנתונים, כמו באסטרטגיה החופשית)
        once = getattr(strategy, "ONCE_PER_DAY", False)
        if callable(once):
            once = once(close)
        if once:
            today = now_str[:10]
            if any(t["time"][:10] == today for t in account.trades):
                continue

        if getattr(strategy, "NEEDS_VOLUME", False):
            if volume is None:
                continue  # אין נתוני נפח, מדלגים על האסטרטגיה הזאת
            decisions = strategy.decide(close, set(account.positions), volume=volume)
        else:
            decisions = strategy.decide(close, set(account.positions))

        for d in decisions:
            symbol = d["symbol"]
            if symbol not in prices.index:
                continue
            price = float(prices[symbol])
            if price != price:  # מחיר חסר
                continue

            if d["action"] == "BUY":
                fraction = d.get("fraction", BUY_FRACTION)
                amount = START_CASH_USD * fraction
                account.buy(symbol, amount / price, price, now_str,
                            d["reason"], fee=amount * FEE_RATE)
            elif d["action"] == "SELL":
                if symbol not in account.positions:
                    continue  # אי אפשר למכור מה שלא מחזיקים
                qty = account.positions[symbol]["qty"]
                account.sell(symbol, qty, price, now_str,
                             d["reason"], fee=qty * price * FEE_RATE)


if __name__ == "__main__":
    # בדיקה קטנה על חשבונות חדשים. נשמרת לקובץ בדיקה ולא נוגעת במצב האמיתי.
    import sys
    from bidi import get_display
    from history import get_daily_history
    from portfolio import TEST_FILE, save_state

    sys.stdout.reconfigure(encoding="utf-8")
    history = get_daily_history()
    close = history["Close"]
    volume = history["Volume"]
    accounts = {}
    now_str = str(close.index[-1].date())

    run_strategies(close, now_str, accounts, volume=volume)

    last_prices = close.iloc[-1]
    for name, acc in accounts.items():
        print("Account:", name)
        print("  cash: $%.2f" % acc.cash, "| positions:", len(acc.positions),
              "| total value: $%.2f" % acc.value(last_prices))
        for t in acc.trades:
            print("  ", t["action"], t["symbol"], "qty", round(t["qty"], 4),
                  "price", round(t["price"], 2), "fee", round(t["fee"], 3))
        if acc.trades:
            print()
            print("Reason for the first trade:")
            print(get_display(acc.trades[0]["reason"]))

    save_state(accounts, TEST_FILE)
