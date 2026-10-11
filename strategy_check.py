import sys

from bidi import get_display

from history import get_daily_history


def run_check(strategy):
    """
    בדיקה קטנה לאסטרטגיה: מורידה היסטוריה, מריצה את האסטרטגיה על כל אחד
    מ-5 הימים האחרונים (כאילו רק הנתונים עד אותו יום ידועים),
    ומציגה דוגמה אחת להחלטה עם ההסבר שלה.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    history = get_daily_history()
    close = history["Close"]
    volume = history["Volume"]
    needs_volume = getattr(strategy, "NEEDS_VOLUME", False)

    def run(n):
        if needs_volume:
            return strategy.decide(close.iloc[:n], set(), volume=volume.iloc[:n])
        return strategy.decide(close.iloc[:n], set())

    print("Strategy:", strategy.STRATEGY_NAME)
    print(get_display(strategy.DESCRIPTION))
    print()

    for days_back in range(5):
        n = len(close) - days_back
        print(close.index[n - 1].date(), "- buy signals:", len(run(n)))

    # מחפשים דוגמה להחלטה ב-60 הימים האחרונים
    for days_back in range(60):
        n = len(close) - days_back
        decisions = run(n)
        if decisions:
            print()
            print("Example decision from", close.index[n - 1].date(), ":",
                  decisions[0]["symbol"])
            print(get_display(decisions[0]["reason"]))
            break
