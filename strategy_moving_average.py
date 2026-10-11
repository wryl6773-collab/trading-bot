STRATEGY_NAME = "moving_average"

SHORT = 20  # ממוצע קצר: 20 ימי מסחר
LONG = 50   # ממוצע ארוך: 50 ימי מסחר

DESCRIPTION = (
    "ממוצעים נעים: ממוצע נע הוא הממוצע של מחירי הסגירה בכמה הימים האחרונים. "
    "כשהממוצע הקצר (20 ימים) חוצה למעלה את הארוך (50 ימים), זה רומז שהמגמה "
    "האחרונה חזקה יותר מהמגמה הרחבה, והבוט קונה. כשהוא חוצה למטה, הבוט מוכר. "
    "החולשה: האסטרטגיה מאחרת, ובשוק צדדי היא נותנת הרבה אותות שווא."
)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    short_ma = close.rolling(SHORT).mean()
    long_ma = close.rolling(LONG).mean()

    # חצייה כלפי מעלה: אתמול הקצר היה מתחת או שווה לארוך, והיום מעליו
    crossed_up = (short_ma.shift(1) <= long_ma.shift(1)) & (short_ma > long_ma)
    crossed_down = (short_ma.shift(1) >= long_ma.shift(1)) & (short_ma < long_ma)

    up_today = crossed_up.iloc[-1]
    down_today = crossed_down.iloc[-1]

    decisions = []
    for sym in up_today[up_today].index:
        if sym not in held_symbols:
            s = short_ma[sym].iloc[-1]
            l = long_ma[sym].iloc[-1]
            decisions.append({
                "action": "BUY",
                "symbol": sym,
                "reason": (f"הממוצע ל-{SHORT} ימים ({s:.2f}) חצה למעלה את הממוצע "
                           f"ל-{LONG} ימים ({l:.2f}). זה סימן למגמת עלייה, ולכן קונים."),
            })
    for sym in down_today[down_today].index:
        if sym in held_symbols:
            s = short_ma[sym].iloc[-1]
            l = long_ma[sym].iloc[-1]
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"הממוצע ל-{SHORT} ימים ({s:.2f}) חצה למטה את הממוצע "
                           f"ל-{LONG} ימים ({l:.2f}). זה סימן להיחלשות, ולכן מוכרים."),
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

    decisions = decide(close, set())
    if decisions:
        print()
        print("Example decision:", decisions[0]["symbol"])
        print(get_display(decisions[0]["reason"]))