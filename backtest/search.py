"""Brute-force strategy search on the Nasdaq-100 with an out-of-sample check.

Signals are computed at the close of day t and held from t+1 (no look-ahead).
Each change in position pays COST_BPS. Parameters are ranked on TRAIN only;
TEST (2024-2025) is used once, to grade the finalists.

Usage: python3 backtest/search.py
"""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "nasdaq_data" / "nasdaq_100_daily_2020_2025.csv"
OUT = ROOT / "backtest" / "results.csv"
COST_BPS = 5
TRAIN_END = "2023-12-31"
CASH_RATE = 0.0  # conservative: idle cash earns nothing

px = pd.read_csv(DATA, parse_dates=["date"]).set_index("date")
c, h, l = px["close"], px["high"], px["low"]
ret = c.pct_change().fillna(0.0)
train = ret.index <= TRAIN_END
test = ~train


def stats(r):
    r = r[r.index.notna()]
    n = len(r)
    if n == 0 or r.std() == 0:
        return dict(cagr=0.0, sharpe=0.0, mdd=0.0)
    eq = (1 + r).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1
    sharpe = r.mean() / r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    return dict(cagr=cagr, sharpe=sharpe, mdd=mdd)


def run(pos):
    """pos: target exposure (-1..1) decided at close t. Returns daily strategy returns."""
    pos = pos.fillna(0.0).clip(-1, 1).shift(1).fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.abs())
    return pos * ret + (1 - pos.abs()) * CASH_RATE / 252 - turnover * COST_BPS / 1e4


def rsi(n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def strategies():
    sma = {n: c.rolling(n).mean() for n in range(5, 301, 5)}
    ema = {n: c.ewm(span=n, adjust=False).mean() for n in range(5, 301, 5)}
    # 1. MA crossovers (long/flat and long/short)
    for kind, ma in (("sma", sma), ("ema", ema)):
        for f, s in itertools.combinations(range(5, 301, 5), 2):
            if s < f * 1.5:
                continue
            sig = (ma[f] > ma[s]).astype(float)
            yield f"{kind}_x_{f}_{s}_long", sig
            yield f"{kind}_x_{f}_{s}_ls", sig * 2 - 1
    # 2. Price vs MA trend filter
    for n in range(10, 301, 5):
        yield f"price_gt_sma_{n}", (c > sma[n]).astype(float)
    # 3. Time-series momentum
    for lb in range(5, 253, 5):
        m = c.pct_change(lb)
        yield f"mom_{lb}_long", (m > 0).astype(float)
        yield f"mom_{lb}_ls", np.sign(m)
    # 4. RSI mean reversion
    for n in (2, 3, 5, 7, 10, 14):
        r = rsi(n)
        for lo in (5, 10, 15, 20, 25, 30, 35):
            for hi in (50, 55, 60, 65, 70, 75, 80):
                pos = pd.Series(np.nan, index=c.index)
                pos[r < lo] = 1.0
                pos[r > hi] = 0.0
                yield f"rsi{n}_{lo}_{hi}", pos.ffill()
                # RSI dip-buy only while in a long-term uptrend
                yield f"rsi{n}_{lo}_{hi}_trend200", pos.ffill() * (c > sma[200])
    # 5. Bollinger mean reversion
    for n in (10, 15, 20, 30, 40, 50):
        mu, sd = c.rolling(n).mean(), c.rolling(n).std()
        for k in (1.0, 1.5, 2.0, 2.5):
            pos = pd.Series(np.nan, index=c.index)
            pos[c < mu - k * sd] = 1.0
            pos[c > mu] = 0.0
            yield f"boll_{n}_{k}", pos.ffill()
    # 6. Donchian breakout
    for ent in range(10, 121, 10):
        for ex in range(5, ent + 1, 5):
            hi_, lo_ = h.rolling(ent).max().shift(1), l.rolling(ex).min().shift(1)
            pos = pd.Series(np.nan, index=c.index)
            pos[c > hi_] = 1.0
            pos[c < lo_] = 0.0
            yield f"donch_{ent}_{ex}", pos.ffill()
    # 7. Volatility targeting (always long, size by realized vol)
    for n in (10, 20, 40, 60):
        vol = ret.rolling(n).std() * np.sqrt(252)
        for tgt in (0.10, 0.15, 0.20, 0.25, 0.30):
            yield f"voltgt_{n}_{tgt}", (tgt / vol).clip(0, 1)
            yield f"voltgt_{n}_{tgt}_trend200", (tgt / vol).clip(0, 1) * (c > sma[200])
    # 8. Day-of-week / turn-of-month calendar effects
    dow = pd.Series(c.index.dayofweek, index=c.index)
    for days in itertools.chain.from_iterable(itertools.combinations(range(5), k) for k in (1, 2, 3, 4)):
        # position decided at t applies to t+1, so target the *next* day's weekday
        yield f"dow_{''.join(map(str, days))}", dow.shift(-1).isin(days).astype(float)
    dom = pd.Series(c.index.day, index=c.index)
    for last in (1, 2, 3, 4, 5):
        for first in (1, 2, 3, 4, 5):
            nxt = dom.shift(-1)
            # approximate: next day is in last `last` or first `first` trading days of a month
            month = pd.Series(c.index.to_period("M"), index=c.index)
            rank_fwd = month.groupby(month).cumcount()
            rank_bwd = month.groupby(month).cumcount(ascending=False)
            on = ((rank_bwd.shift(-1) < last) | (rank_fwd.shift(-1) < first)).astype(float)
            yield f"tom_{last}_{first}", on


def main():
    bh = stats(ret[train]), stats(ret[test])
    rows = []
    for name, pos in strategies():
        r = run(pos)
        tr, te = stats(r[train]), stats(r[test])
        rows.append(dict(strategy=name,
                         train_cagr=tr["cagr"], train_sharpe=tr["sharpe"], train_mdd=tr["mdd"],
                         test_cagr=te["cagr"], test_sharpe=te["sharpe"], test_mdd=te["mdd"],
                         exposure=pos.fillna(0).clip(-1, 1).abs().mean()))
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, float_format="%.4f")

    pct = lambda x: f"{x:7.1%}"
    print(f"Tested {len(df):,} strategies  (cost {COST_BPS} bps/trade, train <= {TRAIN_END})\n")
    print(f"Buy & hold NDX  train: CAGR {pct(bh[0]['cagr'])} Sharpe {bh[0]['sharpe']:.2f} MDD {pct(bh[0]['mdd'])}")
    print(f"                test : CAGR {pct(bh[1]['cagr'])} Sharpe {bh[1]['sharpe']:.2f} MDD {pct(bh[1]['mdd'])}\n")

    top = df.sort_values("train_sharpe", ascending=False).head(20)
    print("Top 20 by TRAIN Sharpe -> how they did on unseen TEST data")
    print(top.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    beat_tr = (df.train_sharpe > bh[0]["sharpe"]).mean()
    beat_te = (df.test_sharpe > bh[1]["sharpe"]).mean()
    beat_both = ((df.train_sharpe > bh[0]["sharpe"]) & (df.test_sharpe > bh[1]["sharpe"])).sum()
    print(f"\nBeat buy&hold Sharpe in train: {beat_tr:.1%}   in test: {beat_te:.1%}   in both: {beat_both}")
    print(f"Top-20-by-train median test Sharpe: {top.test_sharpe.median():.2f}  vs B&H {bh[1]['sharpe']:.2f}")
    print(f"Top-20-by-train median test CAGR:   {top.test_cagr.median():.1%}  vs B&H {bh[1]['cagr']:.1%}")
    print(f"Rank corr(train Sharpe, test Sharpe): {df.train_sharpe.rank().corr(df.test_sharpe.rank()):.2f}")


if __name__ == "__main__":
    main()
