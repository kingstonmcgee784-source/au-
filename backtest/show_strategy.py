"""Show ONE strategy in full: its rules, every trade, and its equity curve with Tradeify
evaluation outcomes. Strategy: at 10:00 ET trade in the direction NQ has moved since the
18:00 ET Globex open; 300-point stop; exit 16:00; 1 MNQ ($2/point, $3.50 costs per trade).

Usage: python3 backtest/show_strategy.py   -> backtest/strategy_trades.csv, backtest/strategy_equity.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from daytrade import build_day_table, load_days

ROOT = Path(__file__).resolve().parent
STOP, QTY, COST = 300.0, 1, 3.50


def main():
    t = build_day_table(load_days())
    trades = []
    for d in t.to_dict("records"):
        move = d["o10"] - d["globex_open"]
        if move == 0:
            continue
        side = 1 if move > 0 else -1
        entry, exit_px, how = d["o10"], d["c15"], "4pm close"
        for h in range(10, 16):
            adverse = entry - d[f"l{h}"] if side > 0 else d[f"h{h}"] - entry
            if adverse >= STOP:
                exit_px, how = entry - side * STOP, f"stop hit {h}:00-{h+1}:00"
                break
        pts = side * (exit_px - entry)
        trades.append(dict(date=d["session"], globex_open_6pm=d["globex_open"], price_10am=entry,
                           direction="LONG" if side > 0 else "SHORT", exit_price=round(exit_px, 2),
                           exit=how, points=round(pts, 2), dollars=round(pts * 2 * QTY - COST * QTY, 2)))
    df = pd.DataFrame(trades)
    df["running_total"] = df.dollars.cumsum().round(2)

    # Tradeify evaluations back to back: start, run until +3000 or -2000 trailing, then start a new one
    evals, start, bal, peak = [], 0, 0.0, 0.0
    for i, r in df.iterrows():
        bal += r.dollars
        if bal <= peak - 2000 or bal >= 3000:
            evals.append(dict(start=df.date[start], end=r.date, result="PASS" if bal >= 3000 else "FAIL",
                              days=i - start + 1))
            start, bal, peak = i + 1, 0.0, 0.0
        else:
            peak = max(peak, bal)
    ev = pd.DataFrame(evals)
    df.to_csv(ROOT / "strategy_trades.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5), dpi=150)
    dates = pd.to_datetime(df.date)
    ax.plot(dates, df.running_total, color="#2563eb", lw=1.6)
    ax.axhline(0, color="#999", lw=0.8)
    for _, e in ev.iterrows():
        x = pd.to_datetime(e.end)
        y = df.running_total[df.date == e.end].iloc[0]
        ax.scatter(x, y, color="#16a34a" if e.result == "PASS" else "#dc2626", s=40, zorder=3)
    ax.set_title("NQ 10am Globex momentum, 1 MNQ: running profit after costs\n"
                 "green dot = simulated Tradeify 50K PASS, red dot = FAIL (evaluations run back to back)")
    ax.set_ylabel("US dollars")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ROOT / "strategy_equity.png")

    wins = df[df.dollars > 0]
    print(f"{len(df)} trades {df.date.iloc[0]} .. {df.date.iloc[-1]}")
    print(f"winners {len(wins)} ({len(wins)/len(df):.0%}), avg win ${wins.dollars.mean():.0f}, "
          f"avg loss ${df[df.dollars <= 0].dollars.mean():.0f}, stops hit {df.exit.str.startswith('stop').sum()}")
    print(f"total ${df.dollars.sum():,.0f}; best day ${df.dollars.max():,.0f}; worst day ${df.dollars.min():,.0f}")
    print(f"\nback-to-back Tradeify evaluations: {(ev.result=='PASS').sum()} passed, {(ev.result=='FAIL').sum()} failed")
    print(ev.to_string(index=False))
    print("\nlast 10 trades:")
    print(df.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
