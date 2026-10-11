import importlib
import json
import os
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

from bidi import get_display

from engine import START_CASH_USD, STRATEGY_MODULES, run_strategies
from history import get_daily_history
from portfolio import DATA_DIR, Account, load_state, save_state

sys.stdout.reconfigure(encoding="utf-8")

# קובץ קטן ששומר עד איזה יום מסחר הבוט כבר עיבד
META_FILE = os.path.join(DATA_DIR, "meta.json")


def show(text=""):
    """מדפיס טקסט בעברית בסדר הנכון בחלון השחור."""
    print(get_display(text))


def load_last_processed():
    if not os.path.exists(META_FILE):
        return None
    with open(META_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("last_processed")


def save_last_processed(day_str):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_processed": day_str}, f)


def print_opening():
    """הודעת פתיחה: מה הבוט עושה ומתי הבורסה האמריקאית פתוחה לפי שעון ישראל."""
    ny = ZoneInfo("America/New_York")
    il = ZoneInfo("Asia/Jerusalem")
    today = datetime.now(ny).date()
    open_il = datetime.combine(today, time(9, 30), tzinfo=ny).astimezone(il)
    close_il = datetime.combine(today, time(16, 0), tzinfo=ny).astimezone(il)

    show("=" * 50)
    show("בוט מסחר וירטואלי - כסף דמיוני בלבד")
    show("הבוט בודק אסטרטגיות מסחר על מחירי מניות אמיתיים.")
    show("זה לא ייעוץ השקעות, ואין כאן שום כסף אמיתי.")
    show(f"שעות המסחר היום לפי שעון ישראל: {open_il:%H:%M} עד {close_il:%H:%M}")
    show("=" * 50)


def main():
    print_opening()

    accounts = load_state()
    for module_name in STRATEGY_MODULES:
        name = importlib.import_module(module_name).STRATEGY_NAME
        if name not in accounts:
            accounts[name] = Account(name, START_CASH_USD)

    show()
    show("מוריד היסטוריית מחירים של כל המניות...")
    history = get_daily_history()
    close = history["Close"]
    volume = history["Volume"]
    last_day = str(close.index[-1].date())
    processed = load_last_processed()

    trades_before = {n: len(a.trades) for n, a in accounts.items()}

    if processed is None:
        show("הפעלה ראשונה: הבוט מתחיל מהיום האחרון ואילך, בלי לסחור על העבר.")
    elif last_day == processed:
        show("אין יום מסחר חדש מאז ההפעלה האחרונה, אז אין מה לעדכן.")
    else:
        new_days = [d for d in close.index if str(d.date()) > processed]
        show(f"מעבד {len(new_days)} ימי מסחר חדשים...")
        for day in new_days:
            known = close.loc[:day]  # רק מה שהיה ידוע עד אותו יום
            known_volume = volume.loc[:day]
            run_strategies(known, str(day.date()), accounts, volume=known_volume)

    save_state(accounts)
    save_last_processed(last_day)

    last_prices = close.iloc[-1]
    show()
    show("מצב החשבונות:")
    for name, acc in accounts.items():
        new_trades = len(acc.trades) - trades_before.get(name, 0)
        print(f"  {name}: value ${acc.value(last_prices):.2f} | cash ${acc.cash:.2f}"
              f" | stocks {len(acc.positions)} | new trades {new_trades}")

    show()
    input(get_display("לחץ Enter כדי לסגור..."))


if __name__ == "__main__":
    main()