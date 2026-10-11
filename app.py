"""
הממשק של הבוט: מפעיל שרת קטן על המחשב שלך (רק אצלך, לא באינטרנט),
פותח את הדפדפן, ומציג את החשבונות בזמן אמת.
"""
import importlib
import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime, time as dtime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

import history as history_mod
import live as live_mod
import prices as prices_mod
from engine import START_CASH_USD, STRATEGY_MODULES, run_strategies
from portfolio import DATA_DIR, Account, load_state, save_state

PORT = 8765
NY = ZoneInfo("America/New_York")
IL = ZoneInfo("Asia/Jerusalem")
META_FILE = os.path.join(DATA_DIR, "meta.json")
SNAP_FILE = os.path.join(DATA_DIR, "daily_values.json")
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)  # כל הקבצים (data וכו') יהיו תמיד ליד הבוט, לא משנה מאיפה הפעלת אותו
IDLE_QUIT_SECONDS = 300  # אם החלון נסגר ואף אחד לא מבקש נתונים 5 דקות, הבוט נסגר

TICK_EVERY = 300         # כל 5 דקות בשעות המסחר האסטרטגיות בודקות את כל השוק ויכולות לקנות ולמכור
LIVE_EVERY = 60          # מחירים חיים של המניות שהחשבונות מחזיקים: כל דקה
DAILY_RETRY_EVERY = 900  # אם נתוני היום עוד לא מוכנים: ניסיון חוזר כל 15 דקות
DAILY_MAX_TRIES = 8      # ומוותרים אחרי 8 ניסיונות (למשל בחג שבו הבורסה סגורה)

lock = threading.RLock()
S = {
    "accounts": {},
    "info": {},          # שם אסטרטגיה -> תיאור
    "last_close": {},    # המחיר האחרון הידוע מהנתונים היומיים
    "live": {},          # מחירים חיים
    "live_time": None,
    "last_processed": None,
    "snapshots": {},     # תאריך -> {אסטרטגיה: שווי}
    "message": "מתחיל...",
    "busy": True,
    "caught_up": False,
    "last_ping": time.time(),
    "pinged": False,
}


def log(text):
    try:
        if sys.stdout is not None and sys.stdout.isatty():
            from bidi import get_display
            text = get_display(text)
    except Exception:
        pass
    try:
        print(text, flush=True)
    except Exception:
        pass


def set_message(text):
    with lock:
        S["message"] = text


# ---------- קבצים ----------
def load_meta():
    if not os.path.exists(META_FILE):
        return None
    with open(META_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("last_processed")


def save_meta(day):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_processed": day}, f)


def load_snapshots():
    if not os.path.exists(SNAP_FILE):
        return {}
    with open(SNAP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshots(snaps):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SNAP_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snaps, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SNAP_FILE)


# ---------- שעות מסחר ----------
def market_open(now=None):
    ny = (now or datetime.now(NY)).astimezone(NY)
    return ny.weekday() < 5 and dtime(9, 30) <= ny.time() < dtime(16, 0)


def next_open():
    """מתי הבורסה נפתחת בפעם הבאה, לפי שעון ישראל (לא מתחשב בחגים)."""
    ny = datetime.now(NY)
    day = ny.date()
    if ny.weekday() < 5 and ny.time() < dtime(9, 30):
        pass
    else:
        day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    opening = datetime.combine(day, dtime(9, 30), tzinfo=NY).astimezone(IL)
    names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    return f"יום {names[opening.weekday()]} ב-{opening:%H:%M}"


def open_window(url):
    """פותח חלון נפרד בצורת אפליקציה (בלי לשוניות וכתובת), ואם לא מצליח, דפדפן רגיל."""
    import shutil
    import subprocess
    for exe in ("msedge", "chrome"):
        path = shutil.which(exe)
        if not path:
            for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
                if not base:
                    continue
                cand = (os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe") if exe == "msedge"
                        else os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
                if os.path.exists(cand):
                    path = cand
                    break
        if path:
            try:
                subprocess.Popen([path, f"--app={url}", "--window-size=1200,860"])
                return
            except Exception:
                pass
    webbrowser.open(url)


def completed_cutoff(now=None):
    """היום האחרון שהנתונים היומיים שלו שלמים. עד 16:15 בניו יורק היום עדיין לא נגמר."""
    ny = (now or datetime.now(NY)).astimezone(NY)
    if ny.time() < dtime(16, 15):
        return str((ny - timedelta(days=1)).date())
    return str(ny.date())


# ---------- עיבוד יומי (כולל השלמה בדיעבד) ----------
def position_prices(close_row, acc):
    out = {}
    for sym, pos in acc.positions.items():
        p = close_row.get(sym)
        out[sym] = float(p) if p is not None and p == p else pos["avg_price"]
    return out


def process_daily():
    """מוריד נתונים יומיים, ומריץ את האסטרטגיות על כל יום שהושלם מאז העיבוד האחרון. מחזיר כמה ימים עובדו."""
    cutoff = completed_cutoff()
    set_message("מוריד היסטוריית מחירים...")
    h = history_mod.get_daily_history()
    close, volume = h["Close"], h["Volume"]
    keep = [str(d.date()) <= cutoff for d in close.index]
    close, volume = close[keep], volume[keep]
    if close.empty:
        return 0
    last_day = str(close.index[-1].date())

    with lock:
        accounts = S["accounts"]
        processed = S["last_processed"]
        snaps = S["snapshots"]

    count = 0
    if processed is None:
        log("הפעלה ראשונה: הבוט מתחיל מהיום האחרון ואילך, בלי לסחור על העבר.")
    elif last_day > processed:
        new_days = [d for d in close.index if str(d.date()) > processed]
        for day in new_days:
            set_message(f"מעבד את יום המסחר {day.date()}...")
            known = close.loc[:day]
            known_vol = volume.loc[:day]
            with lock:
                run_strategies(known, str(day.date()), accounts, volume=known_vol)
                row = known.ffill().iloc[-1]
                snaps[str(day.date())] = {
                    n: round(a.value(position_prices(row, a)), 2)
                    for n, a in accounts.items()
                }
            count += 1

    with lock:
        save_state(accounts)
        save_meta(last_day)
        save_snapshots(snaps)
        S["last_processed"] = last_day
        S["last_close"] = close.ffill().iloc[-1].to_dict()
    return count


def value_of(acc):
    """שווי החשבון לפי המחירים החיים, ואם אין אז לפי הסגירה האחרונה."""
    total = acc.cash
    for sym, pos in acc.positions.items():
        p = S["live"].get(sym)
        if p is None or p != p:
            p = S["last_close"].get(sym)
        if p is None or p != p:
            p = pos["avg_price"]
        total += pos["qty"] * p
    return total


def record_snapshot_if_due():
    """אחרי סגירת הבורסה שומר את שווי כל החשבונות של היום, בשביל טבלת השינוי היומי."""
    ny = datetime.now(NY)
    today = str(ny.date())
    if ny.weekday() >= 5 or ny.time() < dtime(16, 5):
        return
    with lock:
        if S["last_processed"] != today or today in S["snapshots"]:
            return
        S["snapshots"][today] = {n: round(value_of(a), 2) for n, a in S["accounts"].items()}
        save_snapshots(S["snapshots"])


def daily_loop():
    """ההשלמה בדיעבד של ימים שהוחמצו (ועיבוד יום שלם אם הבוט הופעל אחרי הסגירה)."""
    tries, last_try = {}, {}
    while True:
        try:
            cutoff = completed_cutoff()
            with lock:
                processed = S["last_processed"]
            due = processed is None or cutoff > processed
            if due and tries.get(cutoff, 0) < DAILY_MAX_TRIES \
                    and time.time() - last_try.get(cutoff, 0) >= DAILY_RETRY_EVERY:
                tries[cutoff] = tries.get(cutoff, 0) + 1
                last_try[cutoff] = time.time()
                n = process_daily()
                if n:
                    log(f"עובדו {n} ימי מסחר חדשים.")
                    tries[cutoff] = DAILY_MAX_TRIES  # הצלחנו, אין צורך לנסות שוב
            if not due or tries.get(cutoff, 0) >= 1:
                S["caught_up"] = True
            record_snapshot_if_due()
            with lock:
                S["busy"] = False
        except Exception as error:
            set_message(f"שגיאה בעיבוד היומי, מנסה שוב: {error}")
            with lock:
                S["busy"] = False
        time.sleep(60)


# ---------- מסחר חי באמצע היום ----------
def project_volume(vols, ny):
    """נפח היום עד עכשיו הוא חלקי, אז מגדילים אותו לפי כמה מהיום עבר (הערכה גסה)."""
    elapsed = (ny.hour * 60 + ny.minute) - (9 * 60 + 30)
    factor = 390.0 / min(max(elapsed, 30), 390)
    return {s: v * factor for s, v in vols.items()}


def live_tick():
    """בדיקה אחת של האסטרטגיות על מחירי הרגע. כל אסטרטגיה חופשית לקנות ולמכור."""
    import pandas as pd

    ny = datetime.now(NY)
    today = str(ny.date())
    if S.get("live_hist_day") != today:
        set_message("מוריד היסטוריה לפני תחילת המסחר החי...")
        h = history_mod.get_daily_history()
        keep = [str(d.date()) < today for d in h["Close"].index]
        S["live_close"] = h["Close"][keep]
        S["live_volume"] = h["Volume"][keep]
        S["live_hist_day"] = today
    close, volume = S["live_close"], S["live_volume"]
    if close.empty:
        return

    prices, vols, when = live_mod.get_live_snapshot()
    if when is None or when.tz_convert(NY).date() != ny.date():
        set_message("אין נתוני מסחר חיים להיום (חג או עיכוב בנתונים), מדלג.")
        return
    if (datetime.now(NY) - when.tz_convert(NY).to_pydatetime()).total_seconds() > 30 * 60:
        set_message("הנתונים החיים מתעכבים, מדלג עד שיתעדכנו.")
        return

    row = close.ffill().iloc[-1].copy()
    for sym, p in prices.items():
        if sym in row.index:
            row[sym] = p
    vrow = pd.Series(project_volume(vols, ny)).reindex(volume.columns).fillna(0.0)

    ts = pd.Timestamp(today)
    if close.index.tz is not None:
        ts = ts.tz_localize(close.index.tz)
    live_close = pd.concat([close, pd.DataFrame([row.values], index=[ts], columns=close.columns)])
    live_volume = pd.concat([volume, pd.DataFrame([vrow.values], index=[ts], columns=volume.columns)])

    now_str = datetime.now(IL).strftime("%Y-%m-%d %H:%M")
    with lock:
        before = sum(len(a.trades) for a in S["accounts"].values())
        run_strategies(live_close, now_str, S["accounts"], volume=live_volume)
        after = sum(len(a.trades) for a in S["accounts"].values())
        S["live"].update(prices)
        S["live_time"] = when.tz_convert(IL).strftime("%H:%M:%S %d/%m")
        S["last_processed"] = today
        save_state(S["accounts"])
        save_meta(today)
    set_message(f"בדיקה חיה הסתיימה ב-{datetime.now(IL).strftime('%H:%M')}, בוצעו {after - before} עסקאות חדשות.")


def trade_loop():
    while True:
        try:
            if S.get("caught_up") and market_open():
                live_tick()
                time.sleep(TICK_EVERY)
                continue
        except Exception as error:
            set_message(f"שגיאה בבדיקה החיה, מנסה שוב: {error}")
        time.sleep(5 if not S.get("caught_up") else 20)


# ---------- מחירים חיים להצגה ----------
def live_loop():
    """מרענן כל דקה את המחירים של המניות שמוחזקות, כדי שהשווי בלוח יהיה עדכני."""
    first = True
    while True:
        try:
            with lock:
                held = sorted({s for a in S["accounts"].values() for s in a.positions})
            if held and (first or market_open()):
                prices, when = prices_mod.get_latest_prices(held)
                with lock:
                    S["live"].update(prices)
                    S["live_time"] = when.strftime("%H:%M:%S %d/%m") if when else None
            first = False
        except Exception as error:
            set_message(f"שגיאה בקריאת מחירים חיים, מנסה שוב: {error}")
        time.sleep(LIVE_EVERY)


# ---------- נתונים לדפדפן ----------
def build_state():
    with lock:
        live, last_close = S["live"], S["last_close"]

        def price_of(sym, pos):
            for src in (live, last_close):
                p = src.get(sym)
                if p is not None and p == p:
                    return float(p)
            return pos["avg_price"]

        strategies = []
        for name, acc in S["accounts"].items():
            positions, total = [], acc.cash
            for sym, pos in acc.positions.items():
                price = price_of(sym, pos)
                total += pos["qty"] * price
                cost = pos["qty"] * pos["avg_price"]
                positions.append({
                    "symbol": sym, "qty": pos["qty"], "avg_price": pos["avg_price"],
                    "price": price, "pnl": pos["qty"] * price - cost,
                    "pnl_pct": (price / pos["avg_price"] - 1) * 100 if pos["avg_price"] else 0,
                })
            strategies.append({
                "name": name,
                "description": S["info"].get(name, ""),
                "cash": acc.cash, "value": total,
                "pnl": total - START_CASH_USD,
                "pnl_pct": (total / START_CASH_USD - 1) * 100,
                "positions": sorted(positions, key=lambda p: -p["pnl"]),
                "trades_count": len(acc.trades),
                "trades": list(reversed(acc.trades[-60:])),
            })
        snaps = S["snapshots"]
        days = sorted(snaps)[-10:]
        daily = []
        all_days = sorted(snaps)
        for d in reversed(days):
            i = all_days.index(d)
            prev = snaps[all_days[i - 1]] if i > 0 else None
            row = {"date": d, "values": snaps[d], "change": {}}
            if prev:
                for n, v in snaps[d].items():
                    if n in prev:
                        row["change"][n] = round(v - prev[n], 2)
            daily.append(row)
        return {
            "start_cash": START_CASH_USD,
            "market_open": market_open(),
            "next_open": next_open(),
            "now": datetime.now(IL).strftime("%H:%M:%S"),
            "live_time": S["live_time"],
            "last_processed": S["last_processed"],
            "message": S["message"],
            "busy": S["busy"],
            "strategies": strategies,
            "daily": daily,
        }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            S["last_ping"] = time.time()
            S["pinged"] = True
            data = json.dumps(build_state(), ensure_ascii=False).encode("utf-8")
            self.send_bytes(data, "application/json; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "dashboard.html"), "rb") as f:
                self.send_bytes(f.read(), "text/html; charset=utf-8")
        else:
            self.send_error(404)


def port_in_use():
    import socket
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def idle_watcher(server):
    """כשסוגרים את חלון הלוח, הבוט נשמר ונסגר (כמו אפליקציה רגילה)."""
    started = time.time()
    while True:
        time.sleep(15)
        idle = time.time() - S["last_ping"]
        if (S["pinged"] and idle > IDLE_QUIT_SECONDS) or (not S["pinged"] and time.time() - started > 180):
            log("החלון נסגר, שומר ויוצא.")
            with lock:
                save_state(S["accounts"])
            os._exit(0)


def show_error_box(text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "בוט מסחר וירטואלי", 0x10)
    except Exception:
        pass


def main():
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    url = f"http://127.0.0.1:{PORT}"
    if port_in_use():  # הבוט כבר רץ: רק פותחים שוב את החלון שלו
        open_window(url)
        return

    log("בוט מסחר וירטואלי - כסף דמיוני בלבד. זה לא ייעוץ השקעות.")

    accounts = load_state()
    for module_name in STRATEGY_MODULES:
        module = importlib.import_module(module_name)
        S["info"][module.STRATEGY_NAME] = module.DESCRIPTION
        if module.STRATEGY_NAME not in accounts:
            accounts[module.STRATEGY_NAME] = Account(module.STRATEGY_NAME, START_CASH_USD)
    S["accounts"] = accounts
    S["last_processed"] = load_meta()
    S["snapshots"] = load_snapshots()

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=daily_loop, daemon=True).start()
    threading.Thread(target=trade_loop, daemon=True).start()
    threading.Thread(target=live_loop, daemon=True).start()
    threading.Thread(target=idle_watcher, args=(server,), daemon=True).start()

    log(f"הממשק פועל בכתובת {url}")
    if "--no-browser" not in sys.argv:
        open_window(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with lock:
            save_state(S["accounts"])


if __name__ == "__main__":
    # אם הכול יושב בלי חלון שחור, שגיאות נכתבות לקובץ bot.log וגם מוצגות בהודעה
    if sys.stdout is None or sys.stderr is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        logfile = open(os.path.join(DATA_DIR, "bot.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or logfile
        sys.stderr = sys.stderr or logfile
    try:
        main()
    except Exception:
        import traceback
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "bot.log"), "a", encoding="utf-8") as f:
            f.write(datetime.now().isoformat() + "\n" + traceback.format_exc() + "\n")
        show_error_box("הבוט לא הצליח לעלות. הפרטים נשמרו בקובץ data\\bot.log. אפשר לשלוח אותו ל-Claude.")
        raise
