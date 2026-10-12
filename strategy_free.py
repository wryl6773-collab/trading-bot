"""
strategy_free.py - אסטרטגיה 11: "האסטרטגיה החופשית" (תבנית מוכנה).

הרעיון:
1. כל יום הבוט בודק באיזה מצב השוק נמצא (לפי SPY וממוצעי 20/50/200,
   בדיוק באותם כללים של הבדיקה ההיסטורית backtest_regimes.py).
2. לפי "טבלת הכללים" (RULES) הוא בוחר אחת מ-9 האסטרטגיות שכבר בנינו.
3. הוא מפעיל את האסטרטגיה שנבחרה, ומוסיף להסבר של כל עסקה למה היא נבחרה.

מצב נוכחי: טבלת הכללים ריקה. כל עוד היא ריקה, האסטרטגיה לא קונה ולא מוכרת.
אחרי שהבדיקה ההיסטורית תסתיים, ממלאים את RULES וזהו.

הקובץ עוד לא מחובר לבוט (לא נמצא ב-STRATEGY_MODULES שב-engine.py).
מחברים אותו רק אחרי שהכללים מולאו ונבדקו.
"""
import pandas as pd
import yfinance as yf

from backtest_regimes import STRATEGY_HEB, label_regimes

STRATEGY_NAME = "free_style"

# האסטרטגיה הבוחרת יכולה להפעיל גם את "נפח חריג", ולכן מבקשת נתוני נפח
NEEDS_VOLUME = True

# =====================================================================
#  טבלת הכללים: כאן מכניסים את מה שלמדנו מהבדיקה ההיסטורית.
#  בכל שורה: מצב שוק -> שם הקובץ של האסטרטגיה שתופעל בו.
#  None פירושו "עוד לא החלטנו", ובמצב כזה האסטרטגיה לא עושה כלום.
#
#  אפשרויות לבחירה (בלי "קנה והחזק", שהיא רק להשוואה):
#    "strategy_moving_average"  ממוצעים נעים
#    "strategy_momentum"        מומנטום
#    "strategy_mean_reversion"  חזרה לממוצע
#    "strategy_rsi"             RSI
#    "strategy_macd"            MACD
#    "strategy_breakout"        פריצה
#    "strategy_trailing_stop"   מגמה עם סטופ נגרר
#    "strategy_volume"          נפח חריג
#    "strategy_dca"             קנייה הדרגתית
# =====================================================================
RULES = {
    "עלייה רגועה": None,
    "עלייה חזקה": None,
    "דשדוש": None,
    "נפח חריג": None,
    "ירידה": None,
    "סערה": None,
}
# =====================================================================

ALLOWED = {
    "strategy_moving_average", "strategy_momentum", "strategy_mean_reversion",
    "strategy_rsi", "strategy_macd", "strategy_breakout",
    "strategy_trailing_stop", "strategy_volume", "strategy_dca",
}

DESCRIPTION = (
    "האסטרטגיה החופשית: היא לא ממציאה כללי קנייה משלה. "
    "כל יום היא בודקת באיזה מצב השוק נמצא (עלייה, ירידה, דשדוש, סערה וכו'), "
    "לפי הממוצעים של 20, 50 ו-200 ימים של SPY, ובוחרת את האסטרטגיה "
    "שעבדה הכי טוב במצב כזה בבדיקה ההיסטורית. "
    "המצב נקבע לפי מה שהיה ידוע עד אתמול, בלי הצצה לעתיד."
)

_spy_cache = None          # מחירי SPY, נשמרים בזיכרון כדי לא להוריד שוב ושוב
_once_per_day_done = {}    # אסטרטגיות שפועלות פעם ביום: באיזה יום כבר פעלו


def _get_spy(last_day):
    """מוריד את SPY פעם אחת, ומוריד שוב רק אם חסר בו היום האחרון."""
    global _spy_cache
    if _spy_cache is None or _spy_cache.index[-1] < last_day:
        spy = yf.Ticker("SPY").history(period="10y", interval="1d", auto_adjust=True)
        spy.index = spy.index.tz_localize(None).normalize()
        _spy_cache = spy
    return _spy_cache


def current_regime(close):
    """מחזיר את מצב השוק ביום האחרון שב-close (לפי מה שהיה ידוע אתמול)."""
    last_day = pd.Timestamp(close.index[-1]).tz_localize(None).normalize()
    spy = _get_spy(last_day)
    spy = spy[spy.index <= last_day]  # רק עד היום הנוכחי: בלי הצצה לעתיד
    if len(spy) == 0:
        return None
    return label_regimes(spy).iloc[-1]


def decide(close, held_symbols, volume=None):
    """
    close: טבלת מחירי סגירה עד הרגע הנוכחי בלבד.
    held_symbols: המניות שהחשבון מחזיק כרגע.
    volume: טבלת נפח מסחר (נדרשת רק אם נבחרה אסטרטגיית נפח חריג).
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    import importlib

    regime = current_regime(close)
    if regime is None:
        return []  # אין מספיק היסטוריה כדי לדעת מה מצב השוק

    module_name = RULES.get(regime)
    if module_name is None or module_name not in ALLOWED:
        return []  # עוד לא הוחלט מה עושים במצב הזה

    chosen = importlib.import_module(module_name)

    # אסטרטגיה שפועלת פעם ביום (כמו קנייה הדרגתית) תפעל פעם אחת בלבד בכל יום
    today = str(pd.Timestamp(close.index[-1]).date())
    if getattr(chosen, "ONCE_PER_DAY", False):
        if _once_per_day_done.get(module_name) == today:
            return []
        _once_per_day_done[module_name] = today

    if getattr(chosen, "NEEDS_VOLUME", False):
        if volume is None:
            return []
        decisions = chosen.decide(close, held_symbols, volume=volume)
    else:
        decisions = chosen.decide(close, held_symbols)

    name_heb = STRATEGY_HEB.get(chosen.STRATEGY_NAME, chosen.STRATEGY_NAME)
    prefix = f"מצב השוק: {regime}. לכן נבחרה האסטרטגיה {name_heb}. "
    for d in decisions:
        d["reason"] = prefix + d["reason"]
    return decisions


if __name__ == "__main__":
    # בדיקה קטנה: מה מצב השוק היום, ומה הייתה האסטרטגיה החופשית בוחרת
    import sys
    from bidi import get_display
    from history import get_daily_history

    sys.stdout.reconfigure(encoding="utf-8")
    print("Strategy:", STRATEGY_NAME)
    print(get_display(DESCRIPTION))
    print()

    history = get_daily_history()
    close, volume = history["Close"], history["Volume"]

    regime = current_regime(close)
    print(get_display(f"מצב השוק ביום {close.index[-1].date()}: {regime}"))
    filled = sum(1 for v in RULES.values() if v)
    print(get_display(f"שורות מלאות בטבלת הכללים: {filled} מתוך {len(RULES)}"))

    decisions = decide(close, set(), volume=volume)
    if RULES.get(regime) is None:
        print(get_display("לא נבחרה אסטרטגיה למצב הזה עדיין, לכן אין עסקאות. זה תקין."))
    else:
        print("Decisions:", len(decisions))
        if decisions:
            print(get_display(decisions[0]["reason"]))
    print()
    print("OK")
