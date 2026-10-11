STRATEGY_NAME = "mean_reversion"

WINDOW = 20      # כמה ימי מסחר בממוצע ובסטיית התקן
BUY_Z = -2.0     # קונים כשהמחיר נמוך מהממוצע ב-2 סטיות תקן או יותר
BUY_MAX = 5      # לכל היותר 5 קניות חדשות ביום (הנמוכות ביותר)

DESCRIPTION = (
    "חזרה לממוצע: הרעיון הוא שמחיר שנפל הרבה מתחת לממוצע הרגיל שלו נוטה "
    "לחזור כלפי הממוצע. הבוט משווה את מחיר כל מניה לממוצע של 20 הימים "
    "האחרונים, ומודד כמה היא רחוקה ממנו ביחידות של סטיית תקן (כמה המחיר "
    "בדרך כלל זז). מניה שנפלה ב-2 סטיות תקן או יותר מתחת לממוצע נקנית, "
    "והיא נמכרת כשהמחיר חוזר לממוצע. החולשה: לפעמים מניה נופלת כי קרה "
    "משהו אמיתי, ואז היא לא חוזרת אלא ממשיכה לרדת."
)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if len(close) < WINDOW + 1:
        return []

    ma = close.rolling(WINDOW).mean()
    sd = close.rolling(WINDOW).std()
    z = ((close - ma) / sd).iloc[-1].dropna()
    z = z[z.abs() < 100]  # מסנן ערכים חריגים (למשל כשאין שינוי במחיר)

    price = close.iloc[-1]
    avg = ma.iloc[-1]

    decisions = []

    candidates = z[z <= BUY_Z].sort_values().index  # מהנמוכה ביותר
    count = 0
    for sym in candidates:
        if sym in held_symbols:
            continue
        if count >= BUY_MAX:
            break
        decisions.append({
            "action": "BUY",
            "symbol": sym,
            "reason": (f"המחיר ({price[sym]:.2f}) נמוך מהממוצע ל-{WINDOW} ימים "
                       f"({avg[sym]:.2f}) ב-{abs(z[sym]):.1f} סטיות תקן. "
                       f"זו ירידה חדה מהרגיל, והאסטרטגיה מנחשת שהמחיר יחזור "
                       f"כלפי הממוצע, ולכן קונים."),
        })
        count += 1

    for sym in held_symbols:
        if sym in z.index and z[sym] >= 0:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"המחיר ({price[sym]:.2f}) חזר לממוצע ל-{WINDOW} ימים "
                           f"({avg[sym]:.2f}) או מעליו. המחיר חזר, כמו שהאסטרטגיה "
                           f"קיוותה, ולכן מוכרים."),
            })
    return decisions


if __name__ == "__main__":
    # בדיקה קטנה, רצה רק כשמפעילים את הקובץ ישירות
    import sys
    from bidi import get_display
    from history import get_daily_history

    sys.stdout.reconfigure(encoding="utf-8")
    close = get_daily_history()["Close"]

    print("Strategy:", STRATEGY_NAME)
    print(get_display(DESCRIPTION))
    print()

    # מריצים על כל אחד מ-5 הימים האחרונים, כאילו רק הנתונים עד אותו יום ידועים
    for days_back in range(5):
        known = close.iloc[:len(close) - days_back]
        decisions = decide(known, set())
        print(known.index[-1].date(), "- buy signals:", len(decisions))

    # מחפשים דוגמה להחלטה ב-60 הימים האחרונים
    for days_back in range(60):
        known = close.iloc[:len(close) - days_back]
        decisions = decide(known, set())
        if decisions:
            print()
            print("Example decision from", known.index[-1].date(), ":", decisions[0]["symbol"])
            print(get_display(decisions[0]["reason"]))
            break