STRATEGY_NAME = "volume"

# האסטרטגיה הזאת צריכה נתוני נפח מסחר, והמנוע יעביר אותם אליה
NEEDS_VOLUME = True

VOL_DAYS = 20      # משווים את הנפח של היום לממוצע של 20 הימים הקודמים
VOL_MULT = 3.0     # נפח חריג: פי 3 ומעלה מהממוצע
MIN_RISE = 0.02    # ובנוסף המחיר עלה ביום הזה לפחות 2%
EXIT_MA = 10       # מוכרים כשהמחיר יורד מתחת לממוצע של 10 ימים
BUY_MAX = 5        # לכל היותר 5 קניות חדשות ביום (הנפח החריג ביותר)

DESCRIPTION = (
    "נפח חריג: נפח מסחר הוא כמה מניות נסחרו ביום. כשמניה נסחרת פי 3 ויותר "
    "מהרגיל והמחיר שלה עולה בבת אחת, זה לעיתים סימן שגורמים גדולים "
    "(כמו קרנות) נכנסים למניה, או שיש חדשות חשובות. הבוט קונה במצב כזה "
    "ומוכר כשהמחיר יורד מתחת לממוצע של 10 הימים, כלומר ההתלהבות דעכה. "
    "החולשה: לפעמים קפיצה בנפח היא רק רעש חד-פעמי, והמחיר חוזר למטה מהר."
)


def decide(close, held_symbols, volume=None):
    """
    close: טבלת מחירי סגירה, volume: טבלת נפח מסחר (אותו מבנה),
           רק עד הרגע הנוכחי, בלי שום מידע מהעתיד.
    held_symbols: קבוצת המניות שהחשבון מחזיק כרגע.
    מחזיר רשימת החלטות, ולכל אחת הסבר בעברית.
    """
    if volume is None or len(close) < VOL_DAYS + 2:
        return []

    volume = volume.reindex(index=close.index, columns=close.columns)

    # הנפח הממוצע של התקופה שלפני היום (shift(1) מוציא את היום הנוכחי)
    avg_volume = volume.rolling(VOL_DAYS).mean().shift(1).iloc[-1]
    avg_volume = avg_volume.where(avg_volume > 0)  # מונע חלוקה באפס
    ratio = volume.iloc[-1] / avg_volume
    rise = close.iloc[-1] / close.iloc[-2] - 1

    unusual = (ratio >= VOL_MULT) & (rise >= MIN_RISE)
    candidates = ratio[unusual].dropna().sort_values(ascending=False)

    exit_ma = close.rolling(EXIT_MA).mean().iloc[-1]
    price = close.iloc[-1]

    decisions = []

    count = 0
    for sym in candidates.index:
        if sym in held_symbols:
            continue
        if count >= BUY_MAX:
            break
        decisions.append({
            "action": "BUY",
            "symbol": sym,
            "reason": (f"נפח המסחר היום היה פי {ratio[sym]:.1f} מהממוצע של "
                       f"{VOL_DAYS} הימים הקודמים, והמחיר עלה {rise[sym] * 100:.1f}%. "
                       f"נפח חריג יחד עם עלייה מרמז שגורמים גדולים נכנסים "
                       f"למניה, ולכן קונים."),
        })
        count += 1

    for sym in held_symbols:
        if sym in exit_ma.index and price[sym] < exit_ma[sym]:
            decisions.append({
                "action": "SELL",
                "symbol": sym,
                "reason": (f"המחיר ({price[sym]:.2f}) ירד מתחת לממוצע של {EXIT_MA} "
                           f"ימים ({exit_ma[sym]:.2f}). ההתלהבות שהגיעה עם הנפח "
                           f"החריג דעכה, ולכן מוכרים."),
            })
    return decisions


if __name__ == "__main__":
    import sys
    from strategy_check import run_check

    run_check(sys.modules[__name__])
