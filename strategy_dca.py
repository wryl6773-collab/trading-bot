STRATEGY_NAME = "dca"

# סל קבוע של מניות גדולות. הבוט קונה מהן בסבב, מניה אחת בכל שבוע.
BASKET = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "KO", "WMT"]

# כל קנייה היא 5% מההון ההתחלתי (חצי מהרגיל), כדי שהכסף יספיק ליותר שבועות
BUY_FRACTION = 0.05

# בכל יום מסחר מותר לה לקנות פעם אחת בלבד, גם כשהבוט בודק כל כמה דקות
ONCE_PER_DAY = True

DESCRIPTION = (
    "קנייה הדרגתית (DCA): במקום לנסות לנחש מתי המחיר נמוך, הבוט קונה סכום "
    "קבוע בתחילת כל שבוע מסחר, מניה אחת מסל קבוע של מניות גדולות, בסבב. "
    "אין כאן שום ניתוח של המחיר, והאסטרטגיה לא מוכרת. "
    "היתרון: היא מפזרת את הקניות לאורך זמן, כך שקנייה אחת גרועה לא פוגעת "
    "בכל ההון. החולשה: היא לא מגיבה לשום דבר, ובשוק יורד היא ממשיכה לקנות."
)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע (כאן לא משפיע, כי קונים שוב).
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if len(close) < 2:
        return []

    today = close.index[-1].isocalendar()
    yesterday = close.index[-2].isocalendar()
    if (today[0], today[1]) == (yesterday[0], yesterday[1]):
        return []  # אותו שבוע, קונים רק ביום המסחר הראשון של כל שבוע

    symbol = BASKET[today[1] % len(BASKET)]
    if symbol not in close.columns:
        return []
    price = close[symbol].iloc[-1]
    if price != price:  # מחיר חסר
        return []

    return [{
        "action": "BUY",
        "symbol": symbol,
        "fraction": BUY_FRACTION,
        "reason": (f"התחיל שבוע מסחר חדש (שבוע {today[1]} בשנה). לפי הסבב, "
                   f"קונים השבוע את {symbol} בסכום קבוע, במחיר {price:.2f}, "
                   f"בלי קשר למה שקרה למחיר לאחרונה. כך מפזרים את הקניות "
                   f"לאורך זמן."),
    }]


if __name__ == "__main__":
    import sys
    from strategy_check import run_check

    run_check(sys.modules[__name__])
