STRATEGY_NAME = "macd"

FAST = 12      # ממוצע מהיר: 12 ימים
SLOW = 26      # ממוצע איטי: 26 ימים
SIGNAL = 9     # קו האות: ממוצע של 9 ימים על ההפרש
MIN_DAYS = SLOW + SIGNAL
BUY_MAX = 5    # לכל היותר 5 קניות חדשות ביום (החזקות ביותר)

DESCRIPTION = (
    "MACD: מודד את ההפרש בין ממוצע מהיר (12 ימים) לממוצע איטי (26 ימים) "
    "של המחיר. ההפרש הזה נקרא קו ה-MACD, ויש לו ממוצע משלו שנקרא קו האות. "
    "כשקו ה-MACD חוצה למעלה את קו האות, זה רומז שהמומנטום מתחזק והמגמה "
    "מתהפכת כלפי מעלה, והבוט קונה. כשהוא חוצה למטה, הבוט מוכר. "
    "ההבדל מממוצעים נעים רגילים: ה-MACD מגיב מהר יותר לשינוי בתנופה, "
    "אבל גם נותן יותר אותות שווא כשהשוק צדדי."
)


def _macd(close):
    """מחשב את קו ה-MACD ואת קו האות לכל מניה לכל יום."""
    ema_fast = close.ewm(span=FAST, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=SIGNAL, adjust=False).mean()
    return macd, signal


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if len(close) < MIN_DAYS + 1:
        return []

    macd, signal = _macd(close)
    diff = macd - signal
    today = diff.iloc[-1]
    yesterday = diff.iloc[-2]
    price = close.iloc[-1]

    crossed_up = (yesterday <= 0) & (today > 0)
    crossed_down = (yesterday >= 0) & (today < 0)

    decisions = []

    # מדרגים את החצייות כלפי מעלה לפי העוצמה שלהן ביחס למחיר
    strength = (today / price)[crossed_up].dropna().sort_values(ascending=False)
    count = 0
    for sym in strength.index:
        if sym in held_symbols:
            continue
        if count >= BUY_MAX:
            break
        decisions.append({
            "action": "BUY",
            "symbol": sym,
            "reason": (f"קו ה-MACD ({macd[sym].iloc[-1]:.2f}) חצה למעלה את קו האות "
                       f"({signal[sym].iloc[-1]:.2f}). זה סימן שהמומנטום של המניה "
                       f"מתחזק והמגמה מתהפכת כלפי מעלה, ולכן קונים."),
        })
        count += 1

    for sym in held_symbols:
        if sym in crossed_down.index and crossed_down[sym]:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"קו ה-MACD ({macd[sym].iloc[-1]:.2f}) חצה למטה את קו האות "
                           f"({signal[sym].iloc[-1]:.2f}). זה סימן שהמומנטום נחלש, "
                           f"ולכן מוכרים."),
            })
    return decisions


if __name__ == "__main__":
    import sys
    from strategy_check import run_check

    run_check(sys.modules[__name__])
