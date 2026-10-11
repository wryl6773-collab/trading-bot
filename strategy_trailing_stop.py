STRATEGY_NAME = "trailing_stop"

TREND_DAYS = 100     # ממוצע ארוך טווח: 100 ימי מסחר
STOP_WINDOW = 20     # השיא שממנו מודדים את הסטופ: 20 הימים האחרונים
STOP_PCT = 0.10      # מוכרים כשהמחיר יורד 10% מהשיא
BUY_MAX = 5          # לכל היותר 5 קניות חדשות ביום

DESCRIPTION = (
    "מגמה עם סטופ נגרר: הבוט קונה מניה כשהיא חוצה למעלה את הממוצע ל-100 "
    "הימים, כלומר כשמתחילה מגמת עלייה ארוכה, ורק אם היא לא רחוקה מהשיא "
    "האחרון שלה. אחרי הקנייה הוא נותן לרווחים לרוץ, ומוכר רק כשהמחיר "
    "יורד 10% מהשיא של 20 הימים האחרונים. הסטופ 'נגרר': כשהמחיר עולה, "
    "גם נקודת המכירה עולה אחריו. "
    "החולשה: בשוק תנודתי הסטופ יכול להפעיל מכירה ממש לפני שהמחיר חוזר לעלות."
)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if len(close) < TREND_DAYS + 2:
        return []

    ma = close.rolling(TREND_DAYS).mean()
    price = close.iloc[-1]
    high = close.rolling(STOP_WINDOW).max().iloc[-1]
    stop_level = high * (1 - STOP_PCT)

    above_now = close.iloc[-1] > ma.iloc[-1]
    above_prev = close.iloc[-2] > ma.iloc[-2]
    crossed_up = above_now & ~above_prev
    # לא קונים מניה שכבר נמצאת באזור הסטופ, אחרת היא תימכר מיד
    near_high = price >= high * (1 - STOP_PCT / 2)

    strength = (price / ma.iloc[-1] - 1)[crossed_up & near_high].dropna()
    strength = strength.sort_values(ascending=False)

    decisions = []

    count = 0
    for sym in strength.index:
        if sym in held_symbols:
            continue
        if count >= BUY_MAX:
            break
        decisions.append({
            "action": "BUY",
            "symbol": sym,
            "reason": (f"המחיר ({price[sym]:.2f}) חצה למעלה את הממוצע ל-{TREND_DAYS} "
                       f"ימים ({ma[sym].iloc[-1]:.2f}), כלומר מתחילה מגמת עלייה "
                       f"ארוכה, והמחיר קרוב לשיא האחרון שלו. לכן קונים, ומגינים "
                       f"עם סטופ נגרר של {STOP_PCT * 100:.0f}%."),
        })
        count += 1

    for sym in held_symbols:
        if sym in stop_level.index and price[sym] < stop_level[sym]:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"המחיר ({price[sym]:.2f}) ירד יותר מ-{STOP_PCT * 100:.0f}% "
                           f"מהשיא של {STOP_WINDOW} הימים האחרונים ({high[sym]:.2f}). "
                           f"הסטופ הנגרר הופעל, ולכן מוכרים כדי להגן על הרווח."),
            })
    return decisions


if __name__ == "__main__":
    import sys
    from strategy_check import run_check

    run_check(sys.modules[__name__])
