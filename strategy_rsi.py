STRATEGY_NAME = "rsi"

PERIOD = 14        # כמה ימי מסחר בחישוב ה-RSI
OVERSOLD = 30      # מתחת לזה: המניה "נמכרה יותר מדי"
OVERBOUGHT = 70    # מעל זה: המניה "נקנתה יותר מדי"
BUY_MAX = 5        # לכל היותר 5 קניות חדשות ביום

DESCRIPTION = (
    "RSI: מדד שמודד מ-0 עד 100 כמה המניה עלתה או ירדה בעוצמה בימים האחרונים. "
    "מתחת ל-30 נחשבת למניה שנמכרה יותר מדי, ומעל 70 למניה שנקנתה יותר מדי. "
    "הבוט לא קונה כשה-RSI רק נמוך, אלא מחכה שהמדד יעלה בחזרה מעל 30, "
    "כלומר שהירידה התחילה להיעצר, ואז קונה. הוא מוכר כשה-RSI מגיע ל-70 או יותר. "
    "החולשה: במגמת ירידה חזקה, המדד יכול להישאר נמוך הרבה זמן, והאות המוקדם "
    "יוצא שווא."
)


def _rsi(close):
    """מחשב RSI לכל מניה לכל יום."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / PERIOD, adjust=False, min_periods=PERIOD).mean()
    avg_loss = loss.ewm(alpha=1 / PERIOD, adjust=False, min_periods=PERIOD).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if len(close) < PERIOD + 2:
        return []

    rsi = _rsi(close)
    today = rsi.iloc[-1]
    yesterday = rsi.iloc[-2]

    decisions = []

    # קנייה: אתמול ה-RSI היה מתחת ל-30, והיום הוא כבר חזר ל-30 ומעלה
    recovered = (yesterday < OVERSOLD) & (today >= OVERSOLD)
    candidates = yesterday[recovered].sort_values().index  # מהנמוך ביותר
    count = 0
    for sym in candidates:
        if sym in held_symbols:
            continue
        if count >= BUY_MAX:
            break
        decisions.append({
            "action": "BUY",
            "symbol": sym,
            "reason": (f"ה-RSI של המניה היה אתמול {yesterday[sym]:.1f} (מתחת ל-"
                       f"{OVERSOLD}, כלומר נמכרה יותר מדי) והיום עלה ל-"
                       f"{today[sym]:.1f}. הירידה התחילה להיעצר, ולכן קונים."),
        })
        count += 1

    # מכירה: ה-RSI הגיע ל-70 ומעלה
    for sym in held_symbols:
        if sym in today.index and today[sym] >= OVERBOUGHT:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"ה-RSI של המניה הגיע ל-{today[sym]:.1f} (מעל {OVERBOUGHT}, "
                           f"כלומר נקנתה יותר מדי), ויש סיכוי שהעלייה תיעצר. "
                           f"לכן מוכרים."),
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