STRATEGY_NAME = "buy_and_hold"

# סל קבוע של 9 מניות גדולות, בסכומים שווים. הבוט קונה פעם אחת ולא מוכר.
BASKET = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "KO", "WMT"]

DESCRIPTION = (
    "קנה והחזק: הבוט קונה פעם אחת סל קבוע של 9 מניות גדולות, בסכומים שווים, "
    "ולא עושה שום דבר אחר. הוא לא מוכר ולא קונה שוב. "
    "זו אסטרטגיית השוואה: היא עונה על השאלה אם כל האסטרטגיות האחרות "
    "באמת טובות יותר מלא לעשות כלום. אם אסטרטגיה מורכבת מרוויחה פחות "
    "מהאסטרטגיה הזאת, כל המאמץ שלה לא שווה. "
    "שים לב: הסל כולל רק 9 מניות, ולכן הוא לא מייצג את כל השוק."
)


def decide(close, held_symbols):
    """
    close: טבלת מחירי סגירה (שורה לכל יום, עמודה לכל מניה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    decisions = []
    for symbol in BASKET:
        if symbol in held_symbols or symbol not in close.columns:
            continue
        price = close[symbol].iloc[-1]
        if price != price:  # מחיר חסר
            continue
        decisions.append({
            "action": "BUY",
            "symbol": symbol,
            "reason": (f"קנייה חד-פעמית של {symbol} במחיר {price:.2f}, כחלק מסל "
                       f"של 9 מניות גדולות בסכומים שווים. האסטרטגיה מחזיקה "
                       f"ולא מוכרת, והיא משמשת להשוואה לאסטרטגיות האחרות."),
        })
    return decisions


if __name__ == "__main__":
    import sys
    from strategy_check import run_check

    run_check(sys.modules[__name__])
