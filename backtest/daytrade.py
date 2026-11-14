"""Intraday NQ/MNQ strategy search + prop-firm evaluation simulator.

Every trade opens and closes the same session and is flat by 16:00 ET.
Costs: commission per side + slippage per side (in points), both configurable.
Bars are hourly, so if a stop and a target fall inside the same bar we assume
the STOP hit first (pessimistic).

Selection uses TRAIN only. TEST is graded once. A zero-edge coin-flip
strategy is run through the same prop simulator as a baseline, because
eval rules alone produce a non-trivial pass rate with no edge at all.

Usage: python3 backtest/daytrade.py
"""
import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "nasdaq_data" / "nq_futures_1h.csv"
OUT = ROOT / "backtest" / "daytrade_results.csv"

POINT_VALUE = 2.0          # MNQ = $2/pt (NQ = $20/pt)
COMMISSION_SIDE = 0.75     # $ per contract per side
SLIPPAGE_PTS = 0.5         # points per side (2 ticks)
TRAIN_FRAC = 0.6
MIN_TRADES = 40


@dataclass
class PropRules:
    """Defaults resemble a typical $50K futures evaluation. Set to YOUR firm's numbers."""
    profit_target: float = 3000
    trailing_drawdown: float = 2000   # trails the highest end-of-day balance
    daily_loss_limit: float = 1000    # day stops once breached (firm rules vary)
    max_days: int = 60


def load_days():
    df = pd.read_csv(DATA, parse_dates=["time_et"])
    df = df[df.time_et.dt.minute == 0]
    df["date"] = df.time_et.dt.date
    df["hour"] = df.time_et.dt.hour
    # Trading session for date D: 18:00 on D-1 through 16:00 on D.
    df["session"] = (df.time_et + pd.Timedelta(hours=6)).dt.date
    days = {}
    for sess, g in df.groupby("session"):
        g = g.set_index("hour")
        rth = [h for h in range(9, 16) if h in g.index]
        if len(rth) < 7 or 18 not in g.index:
            continue
        days[sess] = g
    return days


def build_day_table(days):
    """One row per session with the prices strategies may look at (all known at entry)."""
    sessions = sorted(days)
    rows = []
    prev_rth_close = None
    for s in sessions:
        g = days[s]
        row = dict(session=s, globex_open=g.loc[18, "open"], prev_close=prev_rth_close)
        for h in range(9, 16):
            row[f"o{h}"], row[f"h{h}"], row[f"l{h}"], row[f"c{h}"] = g.loc[h, ["open", "high", "low", "close"]]
        rows.append(row)
        prev_rth_close = g.loc[15, "close"]
    return pd.DataFrame(rows).dropna().reset_index(drop=True)


def simulate_trade(day, entry_h, side, stop, target):
    """Points P&L (before costs) for one trade, plus worst open loss in points."""
    entry = day[f"o{entry_h}"]
    worst = 0.0
    for h in range(entry_h, 16):
        hi, lo = day[f"h{h}"], day[f"l{h}"]
        adverse = (entry - lo) if side > 0 else (hi - entry)
        favorable = (hi - entry) if side > 0 else (entry - lo)
        if stop and adverse >= stop:
            return -stop, max(worst, stop)
        worst = max(worst, adverse)
        if target and favorable >= target:
            return target, worst
    return side * (day["c15"] - entry), worst


REFS = {"prev_close": "prev_close", "globex_open": "globex_open", "o9": "o9"}


def strategies():
    entries = range(10, 16)
    stops = (0, 25, 50, 100)
    targets = (0, 50, 100, 200)
    # 1. Move-since-reference: follow or fade, optional min move threshold
    for e, ref, mode, sides, thr, st, tg in itertools.product(
            entries, REFS, ("follow", "fade"), ("both", "long", "short"), (0, 25, 75), stops, targets):
        if ref == "o9" and e == 9:
            continue
        yield (f"move_{ref}_{e}_{mode}_{sides}_thr{thr}_s{st}_t{tg}",
               dict(kind="move", entry=e, ref=ref, mode=mode, sides=sides, thr=thr, stop=st, target=tg))
    # 2. Fixed time-of-day bias
    for e, side, st, tg in itertools.product(range(9, 16), (1, -1), stops, targets):
        yield (f"tod_{e}_{'long' if side > 0 else 'short'}_s{st}_t{tg}",
               dict(kind="tod", entry=e, side=side, stop=st, target=tg))
    # 3. First-hour range breakout (enter at bar open after a break of the 9:00 bar range)
    for e, mode, st, tg in itertools.product(range(11, 16), ("follow", "fade"), stops, targets):
        yield (f"orb_{e}_{mode}_s{st}_t{tg}", dict(kind="orb", entry=e, mode=mode, stop=st, target=tg))


def signal(day, p):
    if p["kind"] == "tod":
        return p["side"]
    e = p["entry"]
    if p["kind"] == "orb":
        last = day[f"c{e - 1}"]
        if last > day["h9"]:
            d = 1
        elif last < day["l9"]:
            d = -1
        else:
            return 0
        return d if p["mode"] == "follow" else -d
    move = day[f"o{e}"] - day[REFS[p["ref"]]]
    if abs(move) <= p["thr"] or move == 0:
        return 0
    d = int(np.sign(move)) * (1 if p["mode"] == "follow" else -1)
    if (p["sides"] == "long" and d < 0) or (p["sides"] == "short" and d > 0):
        return 0
    return d


def trade_list(table, p, rng=None):
    """Per-session $ P&L for 1 contract (0 on no-trade days) and worst open loss in $."""
    pnl, worst = np.zeros(len(table)), np.zeros(len(table))
    cost = 2 * COMMISSION_SIDE + 2 * SLIPPAGE_PTS * POINT_VALUE
    for i, day in enumerate(table.to_dict("records")):
        side = rng.choice((-1, 1)) if rng is not None else signal(day, p)
        if side == 0:
            continue
        pts, w = simulate_trade(day, p["entry"], side, p["stop"], p["target"])
        pnl[i] = pts * POINT_VALUE - cost
        worst[i] = w * POINT_VALUE + cost
    return pnl, worst


def prop_eval(pnl, worst, contracts, rules):
    """Start an evaluation on every session; return pass rate, fail rate, median days to pass."""
    n = len(pnl)
    passes, fails, days_to_pass = 0, 0, []
    for start in range(n):
        bal, peak, outcome = 0.0, 0.0, None
        for k, i in enumerate(range(start, min(n, start + rules.max_days))):
            day_worst = min(worst[i] * contracts, rules.daily_loss_limit)
            if bal - day_worst <= peak - rules.trailing_drawdown:
                outcome = "fail"
                break
            bal += max(pnl[i] * contracts, -rules.daily_loss_limit)
            if bal <= peak - rules.trailing_drawdown:
                outcome = "fail"
                break
            peak = max(peak, bal)
            if bal >= rules.profit_target:
                outcome = "pass"
                days_to_pass.append(k + 1)
                break
        if outcome is None and start + rules.max_days > n:
            continue  # ran out of data, not a real outcome
        passes += outcome == "pass"
        fails += outcome != "pass"
    total = passes + fails
    return dict(pass_rate=passes / total if total else np.nan,
                fail_rate=fails / total if total else np.nan,
                median_days=float(np.median(days_to_pass)) if days_to_pass else np.nan,
                n_evals=total)


def summarize(pnl):
    t = pnl[pnl != 0]
    if len(t) == 0:
        return dict(trades=0, exp=0.0, win=0.0, pf=0.0, total=0.0)
    gains, losses = t[t > 0].sum(), -t[t < 0].sum()
    return dict(trades=len(t), exp=t.mean(), win=(t > 0).mean(),
                pf=gains / losses if losses else np.inf, total=t.sum())


def main():
    table = build_day_table(load_days())
    split = int(len(table) * TRAIN_FRAC)
    tr, te = table.iloc[:split], table.iloc[split:]
    print(f"{len(table)} sessions  train {tr.session.iloc[0]}..{tr.session.iloc[-1]}  "
          f"test {te.session.iloc[0]}..{te.session.iloc[-1]}")
    print(f"Costs per MNQ round trip: ${2*COMMISSION_SIDE + 2*SLIPPAGE_PTS*POINT_VALUE:.2f}\n")

    rows = []
    for name, p in strategies():
        a, _ = trade_list(tr, p)
        b, _ = trade_list(te, p)
        sa, sb = summarize(a), summarize(b)
        rows.append(dict(strategy=name, **{f"train_{k}": v for k, v in sa.items()},
                         **{f"test_{k}": v for k, v in sb.items()}))
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, float_format="%.3f")
    ok = df[df.train_trades >= MIN_TRADES]
    print(f"Tested {len(df):,} strategies ({len(ok):,} with >= {MIN_TRADES} train trades)")
    print(f"Profitable after costs  train: {(ok.train_total > 0).mean():.1%}   "
          f"test: {(ok.test_total > 0).mean():.1%}   both: {((ok.train_total > 0) & (ok.test_total > 0)).mean():.1%}")
    print(f"Rank corr train vs test expectancy: {ok.train_exp.rank().corr(ok.test_exp.rank()):.2f}\n")

    # Rank by a t-stat-like score so tiny-sample flukes don't dominate
    ok = ok.assign(score=ok.train_exp / (ok.train_exp.abs() + 1) * np.sqrt(ok.train_trades))
    top = ok.sort_values("score", ascending=False).head(15)
    cols = ["strategy", "train_trades", "train_exp", "train_win", "train_pf",
            "test_trades", "test_exp", "test_win", "test_pf", "test_total"]
    print("Top 15 picked on TRAIN ($/trade per MNQ) -> unseen TEST")
    print(top[cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print(f"\nTop-15 median test expectancy: ${top.test_exp.median():.2f}/trade; "
          f"{(top.test_total > 0).sum()}/15 profitable in test")

    # Prop-eval simulation on TEST for the #1 train pick vs a coin flip with the same exits
    rules = PropRules()
    best_name = top.iloc[0].strategy
    best_p = dict(strategies())[best_name]
    print(f"\nProp eval on TEST: target ${rules.profit_target:,.0f}, trailing DD ${rules.trailing_drawdown:,.0f}, "
          f"daily limit ${rules.daily_loss_limit:,.0f}, max {rules.max_days} days")
    for contracts in (2, 5, 10):
        pnl, worst = trade_list(te, best_p)
        r = prop_eval(pnl, worst, contracts, rules)
        coin = [prop_eval(*trade_list(te, best_p, rng=np.random.default_rng(seed)), contracts, rules)["pass_rate"]
                for seed in range(20)]
        print(f"  {contracts:>2} MNQ  {best_name}: pass {r['pass_rate']:.0%} "
              f"(median {r['median_days']:.0f} days)   coin-flip same exits: pass {np.mean(coin):.0%}")


if __name__ == "__main__":
    main()
