import json
import os

DATA_DIR = "data"
STATE_FILE = os.path.join(DATA_DIR, "state.json")
TEST_FILE = os.path.join(DATA_DIR, "test_state.json")


class Account:
    """חשבון וירטואלי אחד (לכל אסטרטגיה יש חשבון משלה). הכול בדולרים."""

    def __init__(self, name, cash):
        self.name = name
        self.cash = cash
        self.positions = {}  # מניה -> כמות ומחיר קנייה ממוצע
        self.trades = []     # רשימת כל העסקאות

    def buy(self, symbol, qty, price, time_str, reason, fee=0.0):
        cost = qty * price + fee
        if qty <= 0 or cost > self.cash:
            return False  # אין מספיק מזומן
        self.cash -= cost
        pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0.0})
        total_qty = pos["qty"] + qty
        pos["avg_price"] = (pos["qty"] * pos["avg_price"] + qty * price) / total_qty
        pos["qty"] = total_qty
        self.positions[symbol] = pos
        self.trades.append({"time": time_str, "action": "BUY", "symbol": symbol,
                            "qty": qty, "price": price, "fee": fee, "reason": reason})
        return True

    def sell(self, symbol, qty, price, time_str, reason, fee=0.0):
        pos = self.positions.get(symbol)
        if qty <= 0 or pos is None or pos["qty"] < qty:
            return False  # אי אפשר למכור מה שאין
        self.cash += qty * price - fee
        pos["qty"] -= qty
        if pos["qty"] == 0:
            del self.positions[symbol]
        self.trades.append({"time": time_str, "action": "SELL", "symbol": symbol,
                            "qty": qty, "price": price, "fee": fee, "reason": reason})
        return True

    def value(self, prices):
        """שווי כולל = מזומן + שווי המניות לפי המחירים שנתנו."""
        total = self.cash
        for symbol, pos in self.positions.items():
            total += pos["qty"] * prices[symbol]
        return total


def save_state(accounts, path=STATE_FILE):
    """שומר את כל החשבונות לקובץ. כותב קודם לקובץ זמני כדי שכיבוי פתאומי לא ישחית את המצב."""
    os.makedirs(DATA_DIR, exist_ok=True)
    data = {}
    for name, acc in accounts.items():
        data[name] = {"cash": acc.cash, "positions": acc.positions, "trades": acc.trades}
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def load_state(path=STATE_FILE):
    """טוען את החשבונות מהקובץ. אם אין קובץ, מחזיר רשימה ריקה."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    accounts = {}
    for name, d in data.items():
        acc = Account(name, d["cash"])
        acc.positions = d["positions"]
        acc.trades = d["trades"]
        accounts[name] = acc
    return accounts


if __name__ == "__main__":
    # בדיקה קטנה, רצה רק כשמפעילים את הקובץ ישירות
    acc = Account("demo", 550.0)
    acc.buy("AAPL", 1, 100.0, "2026-10-11 10:00", "test buy", fee=1.0)
    acc.sell("AAPL", 1, 110.0, "2026-10-11 11:00", "test sell", fee=1.0)
    print("cash after trades:", round(acc.cash, 2))
    save_state({"demo": acc}, TEST_FILE)
    loaded = load_state(TEST_FILE)
    print("after load:", round(loaded["demo"].cash, 2), "cash,", len(loaded["demo"].trades), "trades")
