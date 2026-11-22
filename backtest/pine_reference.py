"""Python twin of tradingview/nq_afternoon_momentum.pine, run on 5-minute NQ bars.

Use it to check the Pine script: put the strategy on a 5-minute NQ1!/MNQ1! chart
with extended hours on, open Strategy Tester > List of trades, and compare the
dates, directions and entry/exit prices with backtest/expected_trades.csv.
Small price differences are normal (data vendor, MNQ vs NQ); directions must match.

Usage: python3 backtest/pine_reference.py [--refresh]
  --refresh  re-download the last ~60 days of 5-minute NQ bars from Yahoo
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "nasdaq_data" / "nq_futures_5m.csv"
OUT = ROOT / "backtest" / "expected_trades.csv"

ENTRY_MINS, FLAT_MINS, STOP_PTS, GLOBEX_MINS = 10 * 60, 15 * 60 + 58, 300.0, 18 * 60
SKIP = {"2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25", "2026-12-31", "2027-01-01"}
BAR = pd.Timedelta(minutes=5)


def refresh():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/NQ%3DF?interval=5m&range=60d&includePrePost=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"time_et": pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert("America/New_York"),
                       **{k: q[k] for k in ("open", "high", "low", "close", "volume")}}).dropna()
    df["time_et"] = df.time_et.dt.strftime("%Y-%m-%d %H:%M")
    df.to_csv(DATA, index=False)
    print(f"saved {len(df)} bars to {DATA}")


def mins(ts):
    return ts.hour * 60 + ts.minute


def run(df):
    trades, gopen, gtime, traded, pos = [], None, None, False, None
    rows = df.to_dict("records")
    for i, b in enumerate(rows):
        t_open = b["time_et"]
        t_close = t_open + BAR
        om, cm = mins(t_open), mins(t_close)
        prev_om = mins(rows[i - 1]["time_et"]) if i else 0
        prev_cm = mins(rows[i - 1]["time_et"] + BAR) if i else 0
        if om >= GLOBEX_MINS > prev_om:
            gopen, gtime, traded = b["open"], t_open, False
        # stop check on bars after entry (Pine fills stops intrabar)
        if pos and t_open >= pos["entry_time"]:
            hit = b["low"] <= pos["stop"] if pos["side"] > 0 else b["high"] >= pos["stop"]
            if hit:
                pos.update(exit_time=t_close, exit=pos["stop"], reason="stop")
                trades.append(pos)
                pos = None
        weekday = t_close.dayofweek < 5
        fresh = gtime is not None and t_open - gtime < pd.Timedelta(hours=24)
        if (cm >= ENTRY_MINS > prev_cm and cm < FLAT_MINS and weekday and fresh and not traded
                and pos is None and t_close.strftime("%Y-%m-%d") not in SKIP):
            move = b["close"] - gopen
            if move != 0:
                side = 1 if move > 0 else -1
                pos = dict(date=t_close.strftime("%Y-%m-%d"), side="long" if side > 0 else "short",
                           globex_open=gopen, entry_time=t_close, entry=b["close"],
                           stop=b["close"] - side * STOP_PTS)
                pos["side"] = side
            traded = True
        if pos and FLAT_MINS <= cm < 17 * 60:
            pos.update(exit_time=t_close, exit=b["close"], reason="eod")
            trades.append(pos)
            pos = None
    out = pd.DataFrame(trades)
    if out.empty:
        return out
    out["points"] = (out.exit - out.entry) * out.side
    out["side"] = out.side.map({1: "long", -1: "short"})
    return out[["date", "side", "globex_open", "entry_time", "entry", "stop", "exit_time", "exit", "reason", "points"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    if args.refresh or not DATA.exists():
        refresh()
    df = pd.read_csv(DATA, parse_dates=["time_et"])
    trades = run(df)
    trades.to_csv(OUT, index=False, float_format="%.2f")
    if trades.empty:
        print("no trades")
        return 1
    mnq = trades.points * 2.0 * 2 - 2 * 3.50
    print(trades.to_string(index=False))
    print(f"\n{len(trades)} trades, {(trades.points > 0).mean():.0%} winners, "
          f"total {trades.points.sum():.1f} pts = ${mnq.sum():,.0f} at 2 MNQ after costs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
