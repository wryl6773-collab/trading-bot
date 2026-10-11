STRATEGY_NAME = "breakout"

ENTRY_DAYS = 50   # קונים כשהמחיר עובר את השיא של 50 הימים האחרונים
EXIT_DAYS = 20    # מוכרים כשהמחיר יורד מתחת לשפל של 20 הימים האחרונים
BUY_MAX = 5       # לכל היותר 5 קניות חדשות ביום (הפריצות החזקות ביותר)

DESCRIPTION = (
    "פריצה: כשמחיר מניה עובר את השיא הגבוה ביותר של 50 הימים האחרונים, "
    "זה אומר שהקונים חזקים מספיק כדי לשבור 'תקרה' שהמחיר לא עבר חודשיים. "
    "הבוט קונה את הפריצות החזקות ביותר. הוא מוכר כשהמחיר יורד מתחת לשפל "
    "של 20 הימים האחרונים, כלומר המגמה נשברה. "
    "החולשה: פריצות רבות הן 'פריצות שווא', שבהן המחיר חוזר מיד למטה."
)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if len(close) < ENTRY_DAYS + 2:
        return []

    # השיא והשפל של התקופה שלפני היום (shift(1) מוציא את היום הנוכחי מהחישוב)
    prev_high = close.rolling(ENTRY_DAYS).max().shift(1).iloc[-1]
    prev_low = close.rolling(EXIT_DAYS).min().shift(1).iloc[-1]
    price = close.iloc[-1]

    over = (price / prev_high - 1).dropna()
    breakouts = over[over > 0].sort_values(ascending=False)

    decisions = []

    count = 0
    for sym in breakouts.index:
        if sym in held_symbols:
            continue
        if count >= BUY_MAX:
            break
        decisions.append({
            "action": "BUY",
            "symbol": sym,
            "reason": (f"המחיר ({price[sym]:.2f}) עבר את השיא של {ENTRY_DAYS} הימים "
                       f"האחרונים ({prev_high[sym]:.2f}) ב-{breakouts[sym] * 100:.1f}%. "
                       f"זו פריצה כלפי מעלה, ולכן קונים."),
        })
        count += 1

    for sym in held_symbols:
        if sym in prev_low.index and price[sym] < prev_low[sym]:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"המחיר ({price[sym]:.2f}) ירד מתחת לשפל של {EXIT_DAYS} "
                           f"הימים האחרונים ({prev_low[sym]:.2f}). המגמה נשברה, "
                           f"ולכן מוכרים."),
            })
    return decisions


if __name__ == "__main__":
    import sys
    from strategy_check import run_check

    run_check(sys.modules[__name__])
