"""1,000 NQ day-trading strategies ranked directly on Tradeify 50K Growth pass rate.

Each strategy = signal x entry hour x exit hour x stop x position size.
Ranked on TRAIN pass rate; TEST graded once. Luck baseline: the same 1,000 strategies
with random directions, run through the same evaluation simulator.

Usage: python3 backtest/search1k_prop.py
"""
import itertools

import numpy as np
import pandas as pd

import search10k as S
from daytrade import TRAIN_FRAC, build_day_table, load_days

N = 1000
RULES = dict(target=3000.0, dd=2000.0, dll=1250.0, max_days=60)
SIGNALS = [("globex", "follow"), ("globex", "fade"), ("prevclose", "follow"), ("prevclose", "fade"),
           ("o9", "follow"), ("gap", "fade"), ("prevday", "follow"), ("breakout", "fade"),
           ("breakout", "follow"), ("long", "follow")]
SIZES = [("fixed", 1), ("fixed", 2), ("risk", 600)]


def specs():
    out = []
    for (sig, mode), entry, exit_, sm, size in itertools.product(SIGNALS, (9, 10, 11, 13), (12, 14, 16),
                                                                  (0, 0.25, 0.5, 1.0), SIZES):
        if exit_ <= entry or (sig == "o9" and entry == 9) or (size[0] == "risk" and sm == 0):
            continue
        out.append((sig, mode, entry, exit_, sm, size))
    rng = np.random.default_rng(1000)
    return [out[i] for i in sorted(rng.choice(len(out), size=min(N, len(out)), replace=False))], len(out)


def name(s):
    sig, mode, entry, exit_, sm, (kind, v) = s
    size = f"{v} MNQ" if kind == "fixed" else f"risk ${v}"
    return f"{sig}/{mode} {entry}h->{exit_}h stop={sm}atr {size}"


def dollars(book, spec, rand=None):
    sig_kind, mode, entry, exit_, sm, (kind, v) = spec
    t, f = book.t, book.f
    s = S.signal(t, f, sig_kind, entry) * (1 if mode == "follow" else -1)
    s = s.fillna(0).to_numpy(dtype=float).copy()
    s[np.isnan(book.atr)] = 0
    if rand is not None:
        s = np.where(s != 0, rand, 0)
    pl_l, w_l = book.leg(entry, exit_, 1, sm, 0)
    pl_s, w_s = book.leg(entry, exit_, -1, sm, 0)
    pts = np.where(s > 0, pl_l, np.where(s < 0, pl_s, 0.0))
    worst = np.where(s > 0, w_l, np.where(s < 0, w_s, 0.0))
    if kind == "fixed":
        qty = np.full(len(s), float(v))
    else:
        qty = np.clip(np.floor(v / (book.atr * sm * S.PT_VALUE + 2 * S.COST_PTS)), 1, 40)
        qty = np.nan_to_num(qty, nan=1)
    tr = s != 0
    return (np.where(tr, (pts - S.COST_PTS) * S.PT_VALUE * qty, 0.0),
            np.where(tr, (worst + S.COST_PTS) * S.PT_VALUE * qty, 0.0))


def pass_rate(d, w):
    """Vectorised Tradeify eval started on every day: returns (pass rate, fail rate)."""
    n = len(d)
    starts = np.arange(n)
    bal = np.zeros(n)
    peak = np.zeros(n)
    state = np.zeros(n, int)  # 0 running, 1 pass, -1 fail
    for k in range(RULES["max_days"]):
        i = starts + k
        live = (state == 0) & (i < n)
        if not live.any():
            break
        ii = i[live]
        b, p = bal[live], peak[live]
        intraday_fail = b - np.minimum(w[ii], RULES["dll"]) <= p - RULES["dd"]
        b2 = b + np.maximum(d[ii], -RULES["dll"])
        fail = intraday_fail | (b2 <= p - RULES["dd"])
        p2 = np.maximum(p, b2)
        ok = ~fail & (b2 >= RULES["target"])
        st = np.where(fail, -1, np.where(ok, 1, 0))
        bal[live], peak[live], state[live] = b2, p2, st
    counted = (state != 0) | (starts + RULES["max_days"] <= n)  # drop runs cut off by end of data
    s = state[counted]
    return (s == 1).mean(), (s == -1).mean()


def main():
    t = build_day_table(load_days()).reset_index(drop=True)
    f = S.features(t).reset_index(drop=True)
    sp = int(len(t) * TRAIN_FRAC)
    tr = S.Book(t.iloc[:sp].reset_index(drop=True), f.iloc[:sp].reset_index(drop=True))
    te = S.Book(t.iloc[sp:].reset_index(drop=True), f.iloc[sp:].reset_index(drop=True))
    sl, total = specs()
    print(f"train {tr.t.session.iloc[0]}..{tr.t.session.iloc[-1]} | test {te.t.session.iloc[0]}..{te.t.session.iloc[-1]}")
    print(f"testing {len(sl):,} strategies (from {total:,}); Tradeify 50K: +$3,000 target, $2,000 EOD trailing DD, $1,250 DLL\n")
    rng = np.random.default_rng(5)
    rows, rand_best = [], []
    for s in sl:
        dtr, wtr = dollars(tr, s)
        dte, wte = dollars(te, s)
        ptr, ftr = pass_rate(dtr, wtr)
        pte, fte = pass_rate(dte, wte)
        rp = pass_rate(*dollars(tr, s, rand=rng.choice((-1, 1), len(tr.t))))[0]
        rand_best.append(rp)
        rows.append(dict(spec=s, strategy=name(s), train_pass=ptr, test_pass=pte, train_rand=rp,
                         train_total=dtr.sum(), test_total=dte.sum(), trades=int((dtr != 0).sum() + (dte != 0).sum())))
    df = pd.DataFrame(rows)
    df.drop(columns="spec").to_csv(S.ROOT / "backtest" / "search1k_prop_results.csv", index=False, float_format="%.3f")
    print(f"Best TRAIN pass rate, real strategies:    {df.train_pass.max():.0%}")
    print(f"Best TRAIN pass rate, random directions:  {max(rand_best):.0%}   <- luck line")
    print(f"Median TRAIN pass rate real vs random:    {df.train_pass.median():.0%} vs {np.median(rand_best):.0%}")
    print(f"Rank correlation train vs test pass rate: {df.train_pass.rank().corr(df.test_pass.rank()):.2f}\n")

    top = df.sort_values("train_pass", ascending=False).head(15).copy()
    coins = []
    for s in top.spec:
        coins.append(np.mean([pass_rate(*dollars(te, s, rand=np.random.default_rng(k).choice((-1, 1), len(te.t))))[0]
                              for k in range(40)]))
    top["test_coin"] = coins
    print("Top 15 by TRAIN pass rate -> unseen TEST (coin = random directions, same exits and size)")
    print(top[["strategy", "train_pass", "test_pass", "test_coin", "train_total", "test_total"]].to_string(index=False, formatters={
        "train_pass": "{:.0%}".format, "test_pass": "{:.0%}".format, "test_coin": "{:.0%}".format,
        "train_total": "${:,.0f}".format, "test_total": "${:,.0f}".format}))
    print(f"\nTop 15: median TEST pass {top.test_pass.median():.0%} vs coin {np.median(coins):.0%}; "
          f"beat coin in TEST {(top.test_pass > top.test_coin).sum()}/15")

    print("\nCurrent bot (globex/follow 10h->16h, no ATR stop) at 1 and 2 MNQ, 300-pt stop:")
    for q in (1, 2):
        for name_, b in (("train", tr), ("test", te)):
            stop = np.full(len(b.t), 300.0)
            res = []
            for side in (1, -1):
                res.append(S.outcome(b.t, 10, 16, side, stop, np.full(len(b.t), 1e9)))
            sig = np.sign(b.t.o10 - b.t.globex_open).to_numpy()
            pts = np.where(sig > 0, res[0][0], np.where(sig < 0, res[1][0], 0))
            wst = np.where(sig > 0, res[0][1], np.where(sig < 0, res[1][1], 0))
            d = np.where(sig != 0, (pts - S.COST_PTS) * 2 * q, 0.0)
            w = np.where(sig != 0, (wst + S.COST_PTS) * 2 * q, 0.0)
            coin = np.mean([pass_rate(*(lambda r: (np.where(r > 0, (res[0][0] - S.COST_PTS) * 2 * q, (res[1][0] - S.COST_PTS) * 2 * q),
                                                    np.where(r > 0, (res[0][1] + S.COST_PTS) * 2 * q, (res[1][1] + S.COST_PTS) * 2 * q)))
                                        (np.random.default_rng(k).choice((-1, 1), len(b.t))))[0] for k in range(40)])
            p, fl = pass_rate(d, w)
            print(f"  {q} MNQ {name_:5}: pass {p:.0%}, fail {fl:.0%}, coin pass {coin:.0%}")


if __name__ == "__main__":
    main()
