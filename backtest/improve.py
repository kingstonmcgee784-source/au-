"""A small, pre-declared set of improvements to the 13:00 Globex-momentum rule.

Only a handful of variants, chosen for a reason before looking at results, to keep
data-snooping low. Ranked on TRAIN; TEST reported once, with a coin-flip baseline
for the Tradeify 50K Growth pass rate.

Variants
  base        13:00 entry, follow move since 18:00 Globex open, hold to 16:00
  am10        same idea at 10:00
  am10_pm13   enter 10:00, re-check at 13:00 (stay or flip), hold to 16:00
  thr_k       base, but skip days whose move is smaller than k x 20-day avg range
  agree       base, only when overnight move and the 9:00-13:00 move agree
  volstop     base, stop = 0.75 x 20-day avg range, size so max loss <= $1,200

Usage: python3 backtest/improve.py
"""
import numpy as np
import pandas as pd

from daytrade import COMMISSION_SIDE, POINT_VALUE, SLIPPAGE_PTS, TRAIN_FRAC, PropRules, build_day_table, load_days

RULES = PropRules(profit_target=3000, trailing_drawdown=2000, daily_loss_limit=1250, max_days=60)
RISK_PER_TRADE = 1200.0
FIXED_STOP, FIXED_QTY = 300.0, 2
COST = 2 * COMMISSION_SIDE + 2 * SLIPPAGE_PTS * POINT_VALUE  # per contract round trip


def path_pnl(day, entry_h, side, stop):
    """Points from entry at open of entry_h to 16:00 close, stop checked bar by bar. Returns (pts, worst)."""
    entry, worst = day[f"o{entry_h}"], 0.0
    for h in range(entry_h, 16):
        adverse = (entry - day[f"l{h}"]) if side > 0 else (day[f"h{h}"] - entry)
        if adverse >= stop:
            return -stop, stop
        worst = max(worst, adverse)
    return side * (day["c15"] - entry), worst


def leg(day, h_in, h_out, side, stop):
    """Points for a leg from open of h_in to open of h_out (or 16:00 close if h_out == 16)."""
    entry, worst = day[f"o{h_in}"], 0.0
    for h in range(h_in, h_out):
        adverse = (entry - day[f"l{h}"]) if side > 0 else (day[f"h{h}"] - entry)
        if adverse >= stop:
            return -stop, stop, True
        worst = max(worst, adverse)
    exit_px = day["c15"] if h_out == 16 else day[f"o{h_out}"]
    return side * (exit_px - entry), worst, False


def daily(table, variant, rng=None):
    """$ P&L and worst open loss per session for a variant (0 = no trade)."""
    rng_ = (table[[f"h{h}" for h in range(9, 16)]].max(axis=1) - table[[f"l{h}" for h in range(9, 16)]].min(axis=1))
    avg_rng = rng_.rolling(20).mean().shift(1)  # only past days
    pnl, worst = np.zeros(len(table)), np.zeros(len(table))
    for i, day in enumerate(table.to_dict("records")):
        ar = avg_rng.iloc[i]
        if np.isnan(ar):
            continue
        name, _, arg = variant.partition("_")
        stop, qty = FIXED_STOP, FIXED_QTY
        move13 = day["o13"] - day["globex_open"]
        side = int(np.sign(move13))
        if variant == "am10":
            side = int(np.sign(day["o10"] - day["globex_open"]))
            entry_h = 10
        else:
            entry_h = 13
        if name == "thr" and abs(move13) < float(arg) * ar:
            side = 0
        if variant == "agree" and np.sign(day["o13"] - day["o9"]) != np.sign(move13):
            side = 0
        if variant == "volstop":
            stop = 0.75 * ar
            qty = int(RISK_PER_TRADE // (stop * POINT_VALUE + COST))
        if rng is not None and side != 0:
            side = rng.choice((-1, 1))
        if variant == "am10_pm13":
            s1 = int(np.sign(day["o10"] - day["globex_open"]))
            if rng is not None:
                s1 = rng.choice((-1, 1))
            if s1 == 0:
                continue
            p1, w1, stopped = leg(day, 10, 13, s1, stop)
            pts, w, n_trades = p1, w1, 1
            if not stopped:
                s2 = s1 if rng is not None else (int(np.sign(move13)) or s1)
                if s2 == s1:  # just keep holding; recompute as one leg 10 -> 16
                    pts, w, _ = leg(day, 10, 16, s1, stop)
                else:
                    p2, w2, _ = leg(day, 13, 16, s2, stop)
                    pts, w, n_trades = p1 + p2, max(w1, w2 - p1), 2
            pnl[i] = pts * POINT_VALUE * qty - COST * qty * n_trades
            worst[i] = (w * POINT_VALUE + COST) * qty
            continue
        if side == 0 or qty < 1:
            continue
        pts, w = path_pnl(day, entry_h, side, stop)
        pnl[i] = pts * POINT_VALUE * qty - COST * qty
        worst[i] = (w * POINT_VALUE + COST) * qty
    return pnl, worst


def prop_pass(pnl, worst, rules=RULES):
    n, outcomes = len(pnl), []
    for start in range(n):
        bal = peak = 0.0
        res = None
        for i in range(start, min(n, start + rules.max_days)):
            if bal - min(worst[i], rules.daily_loss_limit) <= peak - rules.trailing_drawdown:
                res = 0
                break
            bal += max(pnl[i], -rules.daily_loss_limit)
            if bal <= peak - rules.trailing_drawdown:
                res = 0
                break
            peak = max(peak, bal)
            if bal >= rules.profit_target:
                res = 1
                break
        if res is None and start + rules.max_days > n:
            continue
        outcomes.append(res or 0)
    return float(np.mean(outcomes)) if outcomes else np.nan


def stats(pnl):
    t = pnl[pnl != 0]
    eq = np.cumsum(pnl)
    dd = (np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()
    sharpe = pnl.mean() / pnl.std() * np.sqrt(252) if pnl.std() else 0
    pf = t[t > 0].sum() / -t[t < 0].sum() if (t < 0).any() else np.inf
    return dict(trades=len(t), win=(t > 0).mean(), per_trade=t.mean(), total=pnl.sum(), pf=pf, sharpe=sharpe, max_dd=dd)


VARIANTS = ["base", "am10", "am10_pm13", "thr_0.1", "thr_0.25", "thr_0.5", "agree", "volstop"]


def main():
    table = build_day_table(load_days())
    split = int(len(table) * TRAIN_FRAC)
    parts = {"train": table.iloc[:split].reset_index(drop=True), "test": table.iloc[split:].reset_index(drop=True)}
    print(f"train {parts['train'].session.iloc[0]}..{parts['train'].session.iloc[-1]}   "
          f"test {parts['test'].session.iloc[0]}..{parts['test'].session.iloc[-1]}   "
          f"(default size {FIXED_QTY} MNQ, stop {FIXED_STOP:.0f} pts)\n")
    rows = []
    for v in VARIANTS:
        row = dict(variant=v)
        for name, tab in parts.items():
            pnl, worst = daily(tab, v)
            s = stats(pnl)
            row.update({f"{name}_{k}": x for k, x in s.items()})
            row[f"{name}_pass"] = prop_pass(pnl, worst)
            row[f"{name}_coin"] = np.mean([prop_pass(*daily(tab, v, rng=np.random.default_rng(k))) for k in range(30)])
        rows.append(row)
    df = pd.DataFrame(rows)
    for name in ("train", "test"):
        cols = ["variant"] + [f"{name}_{c}" for c in ("trades", "win", "per_trade", "total", "pf", "sharpe", "max_dd", "pass", "coin")]
        out = df[cols].copy()
        out.columns = ["variant", "trades", "win%", "$/trade", "total $", "PF", "Sharpe", "maxDD $", "pass", "coin"]
        print(name.upper())
        print(out.to_string(index=False, formatters={
            "win%": "{:.0%}".format, "$/trade": "{:,.1f}".format, "total $": "{:,.0f}".format,
            "PF": "{:.2f}".format, "Sharpe": "{:.2f}".format, "maxDD $": "{:,.0f}".format,
            "pass": "{:.0%}".format, "coin": "{:.0%}".format}))
        print()
    best = df.sort_values("train_sharpe", ascending=False).iloc[0]
    print(f"Best on TRAIN by Sharpe: {best.variant}  ->  TEST Sharpe {best.test_sharpe:.2f}, "
          f"pass {best.test_pass:.0%} vs coin {best.test_coin:.0%}")


if __name__ == "__main__":
    main()
