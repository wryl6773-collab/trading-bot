"""
strategy_free.py - אסטרטגיה 11: "האסטרטגיה החופשית" (תבנית מוכנה).

הרעיון:
1. כל יום הבוט בודק באיזה מצב השוק נמצא (לפי SPY וממוצעי 20/50/200,
   בדיוק באותם כללים של הבדיקה ההיסטורית backtest_regimes.py).
2. לפי "טבלת הכללים" (RULES) הוא בוחר אחת מ-9 האסטרטגיות שכבר בנינו.
3. הוא מפעיל את האסטרטגיה שנבחרה, ומוסיף להסבר של כל עסקה למה היא נבחרה.

מצב נוכחי: טבלת הכללים מולאה לפי הבדיקה ההיסטורית (data/regime_report.txt),
והאסטרטגיה מחוברת לבוט (נמצאת ב-STRATEGY_MODULES שב-engine.py).
בקצרה: בשוק עולה או מדשדש - מומנטום. בשוק יורד או סוער - חזרה לממוצע.
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
    # לפי הבדיקה ההיסטורית (5 שנים, 2021-2026), data/regime_report.txt:
    "עלייה רגועה": "strategy_momentum",       # מומנטום ראשונה ב-5 השנים (בחצי השני שנייה, צמוד)
    "עלייה חזקה": "strategy_momentum",        # מומנטום ניצחה בשני החצאים - התוצאה הכי יציבה
    "דשדוש": "strategy_momentum",             # מומנטום ראשונה ב-5 השנים (בחצי הראשון RSI)
    "נפח חריג": "strategy_momentum",          # מומנטום ראשונה, אבל רק 64 ימים - פחות אמין
    "ירידה": "strategy_mean_reversion",       # חזרה לממוצע ראשונה (94 מתוך 95 הימים היו בחצי הראשון)
    "סערה": "strategy_mean_reversion",        # חזרה לממוצע ראשונה ב-5 השנים (בחצי השני DCA, 25 ימים בלבד)
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
_spy_fetched_at = None     # מתי הורדנו את SPY בפעם האחרונה
SPY_REFRESH_MINUTES = 30   # אם חסר בו היום האחרון, מורידים שוב לכל היותר פעם בחצי שעה


def _as_day(value):
    """הופך תאריך/שעה (עם אזור זמן או בלי) ליום בלבד, בלי אזור זמן."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _get_spy(last_day):
    """מוריד את SPY פעם אחת, ומוריד שוב רק אם חסר בו היום האחרון."""
    global _spy_cache, _spy_fetched_at
    now = pd.Timestamp.now()
    stale = (_spy_fetched_at is None
             or now - _spy_fetched_at > pd.Timedelta(minutes=SPY_REFRESH_MINUTES))
    if _spy_cache is None or (_spy_cache.index[-1] < last_day and stale):
        spy = yf.Ticker("SPY").history(period="10y", interval="1d", auto_adjust=True)
        if spy is None or spy.empty:
            if _spy_cache is None:
                return None
        else:
            index = pd.DatetimeIndex(spy.index)
            if index.tz is not None:
                index = index.tz_localize(None)
            spy.index = index.normalize()
            _spy_cache = spy[~spy.index.duplicated(keep="last")]
        _spy_fetched_at = now
    return _spy_cache


def _regime_and_module(close):
    """מצב השוק ביום האחרון שב-close, ושם האסטרטגיה שנבחרה לו (או None)."""
    regime = current_regime(close)
    if regime is None:
        return None, None
    module_name = RULES.get(regime)
    if module_name not in ALLOWED:
        return regime, None
    return regime, module_name


def ONCE_PER_DAY(close):
    """
    המנוע (engine.py) שואל את זה לפני כל הפעלה: אם האסטרטגיה שנבחרה להיום
    פועלת רק פעם ביום (כמו קנייה הדרגתית), המנוע בודק בהיסטוריית העסקאות
    של החשבון אם כבר הייתה עסקה היום. כך זה עובד גם בענן, שבו כל סבב מתחיל מחדש.
    """
    import importlib
    _, module_name = _regime_and_module(close)
    if module_name is None:
        return False
    return bool(getattr(importlib.import_module(module_name), "ONCE_PER_DAY", False))


def current_regime(close):
    """מחזיר את מצב השוק ביום האחרון שב-close (לפי מה שהיה ידוע אתמול)."""
    if len(close.index) == 0:
        return None
    last_day = _as_day(close.index[-1])
    spy = _get_spy(last_day)
    if spy is None:
        return None
    spy = spy[spy.index <= last_day]  # רק עד היום הנוכחי: בלי הצצה לעתיד
    if len(spy) == 0:
        return None
    regime = label_regimes(spy).iloc[-1]
    if regime is None or regime != regime:  # אין מספיק היסטוריה
        return None
    return regime


def decide(close, held_symbols, volume=None):
    """
    close: טבלת מחירי סגירה עד הרגע הנוכחי בלבד.
    held_symbols: המניות שהחשבון מחזיק כרגע.
    volume: טבלת נפח מסחר (נדרשת רק אם נבחרה אסטרטגיית נפח חריג).
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    import importlib

    regime, module_name = _regime_and_module(close)
    if module_name is None:
        return []  # אין מספיק היסטוריה, או שעוד לא הוחלט מה עושים במצב הזה

    chosen = importlib.import_module(module_name)
    # הערה: "פעם ביום" נבדק במנוע (ראו ONCE_PER_DAY למעלה), לא כאן.

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
