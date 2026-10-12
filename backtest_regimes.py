"""
backtest_regimes.py - בדיקה היסטורית: איזו אסטרטגיה עבדה הכי טוב בכל מצב שוק.

מה הקובץ עושה:
1. מוריד כמה שנים של מחירים יומיים (כל מניות S&P 500 + SPY שמייצג את השוק).
2. מריץ את 10 האסטרטגיות האמיתיות של הבוט, יום אחרי יום, כמו בבוט עצמו
   (כל יום רואות רק מה שהיה ידוע עד אותו יום, בלי הצצה לעתיד).
3. בכל יום מסמן באיזה מצב השוק היה (לפי 20/50/200 של SPY, כפי שהיה ידוע ביום הקודם).
4. מחשב לכל מצב שוק: כמה כל אסטרטגיה הרוויחה או הפסידה בממוצע.
5. מחלק את התקופה לשני חצאים, כדי לבדוק אם התוצאה חוזרת או שהיא מקרית.

לא נוגע במצב האמיתי של הבוט (state.json). שומר דוח בעברית ב-data/regime_report.txt
"""
import os
import sys
import time

import pandas as pd
import yfinance as yf
from bidi import get_display

from engine import STRATEGY_MODULES, START_CASH_USD, run_strategies
from history import get_daily_history
from portfolio import DATA_DIR

# ---- הגדרות (אפשר לשנות בקלות) ----
TEST_YEARS = 5         # כמה שנים בודקים
WARMUP_YEARS = 1       # שנה נוספת לפני כן, רק כדי שיהיו מספיק נתונים לממוצע 200
TAIL_DAYS = 300        # כמה ימים אחורה האסטרטגיות רואות בכל יום (מספיק לכולן, ומאיץ)

# כללי מצב השוק (אותם כללים כמו ב-regime.py)
SHORT, MEDIUM, LONG = 20, 50, 200
STRONG_MOVE = 0.03     # עלייה של יותר מ-3% ב-20 ימים = עלייה חזקה
STORM_VOL = 0.25       # תנודתיות שנתית מעל 25% = סערה
VOLUME_SPIKE = 1.5     # נפח פי 1.5 מהממוצע = חריג

REPORT_FILE = os.path.join(DATA_DIR, "regime_report.txt")

STRATEGY_HEB = {
    "moving_average": "ממוצעים נעים",
    "momentum": "מומנטום",
    "mean_reversion": "חזרה לממוצע",
    "rsi": "RSI",
    "macd": "MACD",
    "breakout": "פריצה",
    "trailing_stop": "מגמה עם סטופ נגרר",
    "volume": "נפח חריג",
    "dca": "קנייה הדרגתית (DCA)",
    "buy_and_hold": "קנה והחזק (להשוואה)",
}
REGIME_ORDER = ["עלייה רגועה", "עלייה חזקה", "דשדוש", "נפח חריג", "ירידה", "סערה"]


def label_regimes(spy):
    """מסמן לכל יום את מצב השוק, לפי מה שהיה ידוע בסוף היום הקודם."""
    close, volume = spy["Close"], spy["Volume"]
    ma20 = close.rolling(SHORT).mean()
    ma50 = close.rolling(MEDIUM).mean()
    ma200 = close.rolling(LONG).mean()
    change20 = close / close.shift(SHORT) - 1
    vol = close.pct_change().rolling(SHORT).std() * (252 ** 0.5)
    vratio = volume / volume.shift(1).rolling(SHORT).mean()

    labels = pd.Series("דשדוש", index=close.index)
    up = (close > ma200) & (ma20 > ma50)
    # הסדר חשוב: כלל מאוחר דורס כלל מוקדם, לכן כותבים מהחלש לחזק
    labels[up] = "עלייה רגועה"
    labels[up & (change20 > STRONG_MOVE)] = "עלייה חזקה"
    labels[vratio > VOLUME_SPIKE] = "נפח חריג"
    labels[(close < ma200) & (ma50 < ma200)] = "ירידה"
    labels[vol > STORM_VOL] = "סערה"
    labels[ma200.isna()] = None
    return labels.shift(1)  # היום מסומן לפי אתמול: בלי הצצה לעתיד


def show(text=""):
    print(get_display(text))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    start = time.time()
    total_years = TEST_YEARS + WARMUP_YEARS

    show(f"מוריד {total_years} שנים של מחירים לכל מניות S&P 500 (יכול לקחת כמה דקות)...")
    history = get_daily_history(period=f"{total_years}y")
    close, volume = history["Close"], history["Volume"]

    spy = yf.Ticker("SPY").history(period=f"{total_years}y", interval="1d", auto_adjust=True)
    spy.index = spy.index.tz_localize(None).normalize()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    volume.index = close.index
    regimes = label_regimes(spy).reindex(close.index)

    test_start = close.index[-1] - pd.DateOffset(years=TEST_YEARS)
    test_days = [d for d in close.index if d >= test_start]
    first_pos = close.index.get_loc(test_days[0])
    show(f"תקופת הבדיקה: {test_days[0].date()} עד {test_days[-1].date()} ({len(test_days)} ימי מסחר)")
    show("מריץ את האסטרטגיות יום אחרי יום...")

    accounts = {}
    values = {}  # יום -> שווי כל חשבון
    for i, day in enumerate(test_days):
        pos = first_pos + i
        known = close.iloc[max(0, pos + 1 - TAIL_DAYS):pos + 1]
        known_vol = volume.iloc[max(0, pos + 1 - TAIL_DAYS):pos + 1]
        run_strategies(known, str(day.date()), accounts, volume=known_vol)
        prices = known.iloc[-1].fillna(0)
        values[day] = {n: a.value(prices) for n, a in accounts.items()}
        if i % 100 == 0:
            print(f"  {i}/{len(test_days)} days...  ({round(time.time() - start)} sec)")

    value_table = pd.DataFrame(values).T
    daily_ret = value_table.pct_change().iloc[1:]
    daily_ret["regime"] = regimes.reindex(daily_ret.index)
    daily_ret = daily_ret.dropna(subset=["regime"])

    half = len(daily_ret) // 2
    parts = {"כל התקופה": daily_ret,
             "חצי ראשון": daily_ret.iloc[:half],
             "חצי שני": daily_ret.iloc[half:]}

    lines = []
    lines.append("דוח בדיקה היסטורית: איזו אסטרטגיה עבדה בכל מצב שוק")
    lines.append(f"תקופה: {daily_ret.index[0].date()} עד {daily_ret.index[-1].date()}")
    lines.append("המספר = רווח או הפסד ממוצע ביום, באחוזים, מכל הארנק של האסטרטגיה.")
    lines.append("(כל קנייה היא רק 10% מהארנק, אז המספרים קטנים. מה שחשוב הוא ההשוואה.)")
    lines.append("")

    best = {}
    for part_name, data in parts.items():
        lines.append("=" * 60)
        lines.append(part_name)
        lines.append("=" * 60)
        best[part_name] = {}
        for regime in REGIME_ORDER:
            rows = data[data["regime"] == regime]
            if len(rows) == 0:
                continue
            avg = rows.drop(columns="regime").mean() * 100
            ranked = avg.sort_values(ascending=False)
            pick = next((s for s in ranked.index if s != "buy_and_hold"), None)
            best[part_name][regime] = pick
            lines.append(f"\n{regime} ({len(rows)} ימים, {len(rows) / len(data):.0%} מהזמן):")
            for s in ranked.index:
                mark = "  <-- הכי טובה" if s == pick else ""
                lines.append(f"   {STRATEGY_HEB.get(s, s):<22} {ranked[s]:+.4f}%{mark}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("האם התוצאה חוזרת? (אותה אסטרטגיה מנצחת בשני החצאים)")
    lines.append("=" * 60)
    for regime in REGIME_ORDER:
        a = best["חצי ראשון"].get(regime)
        b = best["חצי שני"].get(regime)
        if a is None or b is None:
            lines.append(f"{regime}: אין מספיק ימים בשני החצאים")
        elif a == b:
            lines.append(f"{regime}: כן ✓  {STRATEGY_HEB[a]} ניצחה בשניהם")
        else:
            lines.append(f"{regime}: לא ✗  חצי ראשון {STRATEGY_HEB[a]}, חצי שני {STRATEGY_HEB[b]}")

    lines.append("")
    lines.append("הסתייגויות חשובות:")
    lines.append("- רשימת המניות היא של היום. חברות שנפלו ויצאו מהמדד בעבר לא נכללות,")
    lines.append("  ולכן התוצאות נראות קצת יותר טובות מהמציאות.")
    lines.append("- מצב שוק עם מעט ימים (למשל פחות מ-30) הוא כמעט מקרי. לא לסמוך עליו.")
    lines.append("- עבר טוב לא מבטיח עתיד טוב.")
    lines.append(f"\nזמן ריצה: {round(time.time() - start)} שניות")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    value_table.to_csv(os.path.join(DATA_DIR, "regime_backtest_values.csv"))

    for line in lines:
        show(line)
    show()
    show(f"הדוח נשמר בקובץ: {REPORT_FILE}")
    show("אפשר לפתוח אותו בפנקס רשימות ולהדביק לי את התוכן.")


if __name__ == "__main__":
    main()
