STRATEGY_NAME = "momentum"

LOOKBACK = 60   # כמה ימי מסחר בודקים את העלייה
SKIP = 5        # מדלגים על 5 הימים האחרונים
BUY_TOP = 5     # קונים את 5 המובילות
KEEP_TOP = 25   # מוכרים מניה שיצאה מחוץ ל-25 המובילות

DESCRIPTION = (
    "מומנטום: הרעיון הוא שמניות שעלו חזק בחודשים האחרונים נוטות להמשיך לעלות "
    "עוד זמן מה. הבוט מדרג את כל המניות לפי העלייה ב-60 ימי המסחר האחרונים "
    "(בלי השבוע האחרון), וקונה את 5 המובילות. הוא מוכר מניה כשהיא כבר לא "
    "בין 25 המובילות, או כשהעלייה שלה הפכה לשלילית. החולשה: כשהשוק מתהפך "
    "פתאום, המניות שעלו הכי הרבה הן לפעמים הראשונות שנופלות."
)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if len(close) < LOOKBACK + SKIP + 1:
        return []

    past = close.iloc[-(LOOKBACK + SKIP + 1)]
    recent = close.iloc[-(SKIP + 1)]
    momentum = (recent / past - 1).dropna()
    ranking = momentum.sort_values(ascending=False)
    ranks = {sym: i + 1 for i, sym in enumerate(ranking.index)}
    total = len(ranking)

    decisions = []

    for sym in ranking.index[:BUY_TOP]:
        if sym not in held_symbols:
            pct = momentum[sym] * 100
            decisions.append({
                "action": "BUY",
                "symbol": sym,
                "reason": (f"המניה דורגה במקום {ranks[sym]} מתוך {total} לפי העלייה "
                           f"ב-{LOOKBACK} ימי המסחר שלפני השבוע האחרון "
                           f"(עלייה של {pct:.1f}%). מומנטום חזק מרמז שהמגמה "
                           f"עשויה להימשך, ולכן קונים."),
            })

    for sym in held_symbols:
        if sym not in ranks:
            continue
        pct = momentum[sym] * 100
        if ranks[sym] > KEEP_TOP:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"המניה ירדה למקום {ranks[sym]} בדירוג המומנטום "
                           f"(מתוך {total}), מחוץ ל-{KEEP_TOP} המובילות. "
                           f"המומנטום שלה נחלש, ולכן מוכרים."),
            })
        elif pct < 0:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"העלייה של המניה ב-{LOOKBACK} ימי המסחר האחרונים "
                           f"הפכה לשלילית ({pct:.1f}%). אין יותר מומנטום "
                           f"חיובי, ולכן מוכרים."),
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
        top = [d["symbol"] for d in decide(known, set())]
        print(known.index[-1].date(), "- top 5:", ", ".join(top))

    decisions = decide(close, set())
    if decisions:
        print()
        print("Example decision:", decisions[0]["symbol"])
        print(get_display(decisions[0]["reason"]))