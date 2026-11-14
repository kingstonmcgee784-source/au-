"""Tune stop and size for the chosen strategy under Tradeify 50K Growth rules.

The strategy itself is fixed (it was the #1 TRAIN pick in daytrade.py):
at 13:00 ET, trade in the direction NQ has moved since the 18:00 ET Globex
open, hold to the 16:00 close. Only the protective stop and the contract
count are tuned here, on TRAIN; TEST is reported once, next to a coin flip.

Usage: python3 backtest/tradeify_sim.py
"""
import numpy as np

from daytrade import PropRules, TRAIN_FRAC, build_day_table, load_days, prop_eval, trade_list

# Tradeify 50K Growth evaluation (verify against your dashboard; firms change rules)
TRADEIFY_50K_GROWTH = PropRules(profit_target=3000, trailing_drawdown=2000,
                                daily_loss_limit=1250, max_days=60)
MAX_MNQ = 40  # 4 NQ = 40 MNQ position cap
STRATEGY = dict(kind="move", entry=13, ref="globex_open", mode="follow", sides="both", thr=0)


def main():
    table = build_day_table(load_days())
    split = int(len(table) * TRAIN_FRAC)
    tr, te = table.iloc[:split], table.iloc[split:]
    rules = TRADEIFY_50K_GROWTH

    grid = []
    for stop in (0, 50, 75, 100, 150):
        p = dict(STRATEGY, stop=stop, target=0)
        pnl, worst = trade_list(tr, p)
        for n in (2, 4, 6, 8, 10, 15, 20):
            r = prop_eval(pnl, worst, n, rules)
            grid.append((r["pass_rate"], stop, n, r["median_days"]))
    grid.sort(reverse=True)
    print("TRAIN pass rate by stop (pts) and MNQ contracts, top 10:")
    for pr, stop, n, md in grid[:10]:
        print(f"  stop {stop:>3}  {n:>2} MNQ  pass {pr:.0%}  median {md:.0f} days")

    _, stop, n, _ = grid[0]
    p = dict(STRATEGY, stop=stop, target=0)
    r = prop_eval(*trade_list(te, p), n, rules)
    coin = [prop_eval(*trade_list(te, p, rng=np.random.default_rng(s)), n, rules)["pass_rate"] for s in range(50)]
    print(f"\nChosen on TRAIN: stop {stop} pts, {n} MNQ")
    print(f"TEST: pass {r['pass_rate']:.0%}, fail {r['fail_rate']:.0%}, median {r['median_days']:.0f} days "
          f"over {r['n_evals']} simulated evals")
    print(f"TEST coin flip, same stop/size: pass {np.mean(coin):.0%} (5th-95th pct "
          f"{np.percentile(coin, 5):.0%}-{np.percentile(coin, 95):.0%})")


if __name__ == "__main__":
    main()
