"""
הרצה בענן (GitHub Actions): סבב אחד ונכבה.

GitHub מפעיל את הקובץ הזה כל כמה דקות. בכל הפעלה הבוט:
1. טוען את המצב השמור (יתרות, פוזיציות, היסטוריה).
2. משלים בדיעבד ימי מסחר שהוחמצו, בלי הצצה לעתיד.
3. אם הבורסה בניו יורק פתוחה עכשיו (כולל בדיקת חגים וימים קצרים),
   מריץ בדיקה חיה אחת של כל האסטרטגיות על מחירי הרגע.
4. אחרי הסגירה שומר את שווי החשבונות של היום.
5. כותב את המצב ואת site_state.json, שדף התוצאות קורא.

אותה לוגיקה כמו ב-app.py (הגרסה המקומית), רק בלי שרת ובלי לולאות.
"""
import importlib
import json
import os
import sys
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

import app  # הפונקציות המשותפות (שמירה, ערכים, בניית המצב לדף)
import history as history_mod
import live as live_mod
import prices as prices_mod
from engine import START_CASH_USD, STRATEGY_MODULES, run_strategies
from portfolio import DATA_DIR, Account, load_state, save_state

NY = ZoneInfo("America/New_York")
IL = ZoneInfo("Asia/Jerusalem")
SITE_STATE_FILE = os.path.join(DATA_DIR, "site_state.json")
STATUS_FILE = os.path.join(DATA_DIR, "run_status.json")
LIVE_PRICES_FILE = os.path.join(DATA_DIR, "live_prices.json")


# ---------- לוח השנה של הבורסה (חגים וימים קצרים) ----------
_simple_cutoff = app.completed_cutoff
_simple_next_open = app.next_open
try:
    import exchange_calendars as xcals
    _CAL = xcals.get_calendar("XNYS")
except Exception:  # אם הספרייה חסרה, נופלים לבדיקה פשוטה בלי חגים
    _CAL = None


def market_open(now=None):
    now = now or datetime.now(NY)
    if _CAL is not None:
        try:
            return bool(_CAL.is_open_on_minute(pd.Timestamp(now).tz_convert("UTC").floor("min")))
        except Exception:
            pass
    ny = now.astimezone(NY)
    return ny.weekday() < 5 and dtime(9, 30) <= ny.time() < dtime(16, 0)


def next_open():
    """מתי הבורסה נפתחת בפעם הבאה, בשעון ישראל (עם חגים)."""
    names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    if _CAL is not None:
        try:
            nxt = _CAL.next_open(pd.Timestamp.now(tz="UTC").floor("min"))
            opening = nxt.tz_convert(IL)
            return f"יום {names[opening.weekday()]} {opening:%d/%m} ב-{opening:%H:%M}"
        except Exception:
            pass
    return _simple_next_open()


def completed_cutoff(now=None):
    """יום המסחר האחרון שהסתיים (רבע שעה אחרי הסגירה, כדי שהנתונים יהיו שלמים)."""
    now = now or datetime.now(NY)
    if _CAL is not None:
        try:
            ts = pd.Timestamp(now).tz_convert("UTC").floor("min") - pd.Timedelta(minutes=15)
            return str(_CAL.previous_close(ts).tz_convert(NY).date())
        except Exception:
            pass
    return _simple_cutoff(now)


# app.build_state משתמש בפונקציות האלה, אז מחליפים אותן בגרסאות המדויקות
app.market_open = market_open
app.next_open = next_open
app.completed_cutoff = completed_cutoff


def log(text):
    print(text, flush=True)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def clean_prices(d):
    return {k: float(v) for k, v in d.items() if v is not None and v == v}


# ---------- שלבי הסבב ----------
def catch_up(close, volume, S):
    """משלים ימי מסחר שלמים שהוחמצו (כמו process_daily ב-app.py)."""
    cutoff = app.completed_cutoff()
    keep = [str(d.date()) <= cutoff for d in close.index]
    close, volume = close[keep], volume[keep]
    if close.empty:
        return 0
    last_day = str(close.index[-1].date())
    processed = S["last_processed"]

    count = 0
    if processed is None:
        log("First run: starting from the last completed trading day, no trading on the past.")
        S["last_processed"] = last_day
    elif last_day > processed:
        for day in [d for d in close.index if str(d.date()) > processed]:
            known = close.loc[:day]
            known_vol = volume.loc[:day]
            run_strategies(known, str(day.date()), S["accounts"], volume=known_vol)
            row = known.ffill().iloc[-1]
            S["snapshots"][str(day.date())] = {
                n: round(a.value(app.position_prices(row, a)), 2) for n, a in S["accounts"].items()
            }
            count += 1
        S["last_processed"] = last_day
    S["last_close"] = clean_prices(close.ffill().iloc[-1].to_dict())
    return count


def live_tick(close_all, volume_all, S):
    """בדיקה חיה אחת על מחירי הרגע (כמו live_tick ב-app.py). מחזיר כמה עסקאות בוצעו."""
    ny = datetime.now(NY)
    today = str(ny.date())
    keep = [str(d.date()) < today for d in close_all.index]
    close, volume = close_all[keep], volume_all[keep]
    if close.empty:
        return 0

    prices, vols, when = live_mod.get_live_snapshot()
    if when is None or when.tz_convert(NY).date() != ny.date():
        S["message"] = "אין נתוני מסחר חיים להיום (חג או עיכוב בנתונים), מדלג."
        return 0
    if (datetime.now(NY) - when.tz_convert(NY).to_pydatetime()).total_seconds() > 30 * 60:
        S["message"] = "הנתונים החיים מתעכבים, מדלג עד שיתעדכנו."
        return 0

    row = close.ffill().iloc[-1].copy()
    for sym, p in prices.items():
        if sym in row.index:
            row[sym] = p
    vrow = pd.Series(app.project_volume(vols, ny)).reindex(volume.columns).fillna(0.0)

    ts = pd.Timestamp(today)
    if close.index.tz is not None:
        ts = ts.tz_localize(close.index.tz)
    live_close = pd.concat([close, pd.DataFrame([row.values], index=[ts], columns=close.columns)])
    live_volume = pd.concat([volume, pd.DataFrame([vrow.values], index=[ts], columns=volume.columns)])

    now_str = datetime.now(IL).strftime("%Y-%m-%d %H:%M")
    before = sum(len(a.trades) for a in S["accounts"].values())
    run_strategies(live_close, now_str, S["accounts"], volume=live_volume)
    after = sum(len(a.trades) for a in S["accounts"].values())
    S["live"].update(clean_prices(prices))
    S["live_time"] = when.tz_convert(IL).strftime("%H:%M:%S %d/%m")
    S["last_processed"] = today
    S["message"] = f"בדיקה חיה ב-{datetime.now(IL):%H:%M}, בוצעו {after - before} עסקאות חדשות."
    return after - before


def refresh_held_prices(S):
    """מחירים עדכניים של המניות שמוחזקות, כדי שהשווי יהיה נכון."""
    held = sorted({s for a in S["accounts"].values() for s in a.positions})
    if not held:
        return
    prices, when = prices_mod.get_latest_prices(held)
    S["live"].update(clean_prices(prices))
    if when is not None:
        S["live_time"] = when.strftime("%H:%M:%S %d/%m")


def snapshot_if_due(S):
    """אחרי סגירת הבורסה שומר את שווי כל החשבונות של היום."""
    ny = datetime.now(NY)
    today = str(ny.date())
    if ny.weekday() >= 5 or ny.time() < dtime(16, 5):
        return False
    if S["last_processed"] != today or today in S["snapshots"]:
        return False
    refresh_held_prices(S)
    S["snapshots"][today] = {n: round(app.value_of(a), 2) for n, a in S["accounts"].items()}
    return True


def main():
    force = "--force" in sys.argv  # הרצה ידנית: תמיד מעדכן את הדף
    S = app.S
    accounts = load_state()
    for module_name in STRATEGY_MODULES:
        module = importlib.import_module(module_name)
        S["info"][module.STRATEGY_NAME] = module.DESCRIPTION
        if module.STRATEGY_NAME not in accounts:
            accounts[module.STRATEGY_NAME] = Account(module.STRATEGY_NAME, START_CASH_USD)
    S["accounts"] = accounts
    S["last_processed"] = app.load_meta()
    S["snapshots"] = app.load_snapshots()
    S["live"] = load_json(LIVE_PRICES_FILE, {})
    status = load_json(STATUS_FILE, {})
    S["live_time"] = status.get("live_time")
    S["last_close"] = status.get("last_close", {})
    S["message"] = status.get("message", "")
    S["busy"] = False

    is_open = market_open()
    processed_before = S["last_processed"]
    need_daily = processed_before is None or app.completed_cutoff() > processed_before
    snapshot_due = (datetime.now(NY).time() >= dtime(16, 5)
                    and processed_before == str(datetime.now(NY).date())
                    and processed_before not in S["snapshots"])
    flag_changed = status.get("market_open") != is_open

    log(f"Market open: {is_open} | last processed: {processed_before} | "
        f"catch-up due: {need_daily} | snapshot due: {snapshot_due}")

    if not (is_open or need_daily or snapshot_due or flag_changed or force):
        log("Nothing to do this round.")
        return

    trades = 0
    if is_open or need_daily:
        h = history_mod.get_daily_history()
        close, volume = h["Close"], h["Volume"]
        n = catch_up(close, volume, S)
        if n:
            log(f"Caught up {n} missed trading day(s).")
            S["message"] = f"הושלמו בדיעבד {n} ימי מסחר שהוחמצו."
        if is_open:
            trades = live_tick(close, volume, S)
            log(f"Live check done, new trades: {trades}")
    if snapshot_due and snapshot_if_due(S):
        log("Saved today's closing values.")
        S["message"] = "הבורסה נסגרה. שווי החשבונות של היום נשמר."
    if not is_open and not S["live"]:
        refresh_held_prices(S)

    save_state(S["accounts"])
    app.save_meta(S["last_processed"])
    app.save_snapshots(S["snapshots"])
    save_json(LIVE_PRICES_FILE, S["live"])

    site = app.build_state()
    site["updated_at"] = datetime.now(IL).strftime("%Y-%m-%d %H:%M")
    site["updated_iso"] = datetime.now(IL).isoformat(timespec="seconds")
    save_json(SITE_STATE_FILE, site)
    save_json(STATUS_FILE, {
        "market_open": is_open,
        "live_time": S["live_time"],
        "last_close": S["last_close"],
        "message": S["message"],
        "updated_at": site["updated_at"],
    })
    log("State and page data saved.")


if __name__ == "__main__":
    main()
