"""Search 10,000 intraday NQ day-trading strategies, with guards against luck.

Guards
  1. Rank on TRAIN only; TEST (most recent ~40%) is graded once.
  2. Luck baseline: the same 10,000 strategies with random directions. The best real
     strategy must beat the best random one, or it is indistinguishable from luck.
  3. Consistency: a candidate must be profitable in each third of TRAIN.
  4. Finalists are run through the Tradeify 50K Growth evaluation simulator vs a coin flip.

Strategy space (sampled to exactly 10,000 with a fixed seed):
  entry hour 9-14 | exit 12:00 / 14:00 / 16:00 close | stop none or 0.25/0.5/1.0 x ATR
  | target none or 0.5/1.0 x ATR | signal (move since Globex open / prior close / 9:00,
  gap, prior-day direction, prior-day high/low breakout, always long/short) follow or fade
  | filter (none, big move, high vol, low vol, with 20-day trend) | sides (both/long/short)
ATR = average 9:00-16:00 range of the previous 20 sessions (no look-ahead).

Usage: python3 backtest/search10k.py [--refresh]
"""
import argparse
import itertools
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from daytrade import TRAIN_FRAC, build_day_table, load_days

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "nasdaq_data" / "nq_futures_1h.csv"
OUT = ROOT / "backtest" / "search10k_results.csv"
N_STRATEGIES = 10_000
COST_PTS = 1.75          # $3.50 round trip per MNQ = 1.75 points
PT_VALUE = 2.0           # MNQ
RISK_DOLLARS = 1200.0    # max loss per trade (Tradeify daily loss limit is 1,250)
NO_STOP_QTY = 2
RULES = dict(target=3000.0, dd=2000.0, dll=1250.0, max_days=60)
HOURS = range(9, 16)


def refresh():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/NQ%3DF?interval=1h&range=730d&includePrePost=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())["chart"]["result"][0]
    q, ny = r["indicators"]["quote"][0], ZoneInfo("America/New_York")
    rows = [[datetime.fromtimestamp(t, ny).strftime("%Y-%m-%d %H:%M"), q["open"][i], q["high"][i], q["low"][i],
             q["close"][i], q["volume"][i]] for i, t in enumerate(r["timestamp"])
            if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])]
    old = pd.read_csv(DATA) if DATA.exists() else pd.DataFrame()
    new = pd.DataFrame(rows, columns=["time_et", "open", "high", "low", "close", "volume"])
    df = pd.concat([old, new]).drop_duplicates("time_et", keep="last").sort_values("time_et")
    df.to_csv(DATA, index=False)
    print(f"hourly bars: {len(df)} ({df.time_et.iloc[0]} .. {df.time_et.iloc[-1]})")


# ---------------------------------------------------------------- features
def features(t):
    f = pd.DataFrame(index=t.index)
    H = t[[f"h{h}" for h in HOURS]].max(axis=1)
    L = t[[f"l{h}" for h in HOURS]].min(axis=1)
    f["atr"] = (H - L).rolling(20).mean().shift(1)
    f["prev_high"], f["prev_low"] = H.shift(1), L.shift(1)
    f["prev_dir"] = np.sign(t.c15 - t.o9).shift(1)
    f["ma20"] = t.c15.rolling(20).mean().shift(1)
    f["atr_med"] = f.atr.rolling(100, min_periods=40).median()
    return f


def outcome(t, entry, exit_, side, stop, target):
    """Per-day points (per contract, before costs) and worst open loss, vectorised over days."""
    n = len(t)
    e = t[f"o{entry}"].to_numpy()
    done = np.zeros(n, bool)
    pts = np.zeros(n)
    worst = np.zeros(n)
    for h in range(entry, exit_):
        hi, lo = t[f"h{h}"].to_numpy(), t[f"l{h}"].to_numpy()
        adverse = (e - lo) if side > 0 else (hi - e)
        fav = (hi - e) if side > 0 else (e - lo)
        stop_hit = ~done & (adverse >= stop)
        pts[stop_hit], worst[stop_hit] = -stop[stop_hit], stop[stop_hit]
        done |= stop_hit
        live = ~done
        worst[live] = np.maximum(worst[live], adverse[live])
        tgt_hit = live & (fav >= target)
        pts[tgt_hit] = target[tgt_hit]
        done |= tgt_hit
    exit_px = t.c15.to_numpy() if exit_ == 16 else t[f"o{exit_}"].to_numpy()
    rest = ~done
    pts[rest] = side * (exit_px[rest] - e[rest])
    return pts, worst


def signal(t, f, kind, entry):
    o = t[f"o{entry}"]
    if kind == "globex":
        return np.sign(o - t.globex_open)
    if kind == "prevclose":
        return np.sign(o - t.prev_close)
    if kind == "o9":
        return np.sign(o - t.o9) if entry > 9 else None
    if kind == "gap":
        return np.sign(t.o9 - t.prev_close)
    if kind == "prevday":
        return f.prev_dir
    if kind == "breakout":
        return pd.Series(np.where(o > f.prev_high, 1, np.where(o < f.prev_low, -1, 0)), index=t.index)
    if kind == "long":
        return pd.Series(1.0, index=t.index)
    if kind == "short":
        return pd.Series(-1.0, index=t.index)
    raise ValueError(kind)


def filt(t, f, kind, entry, sig):
    o = t[f"o{entry}"]
    if kind == "none":
        return pd.Series(True, index=t.index)
    if kind == "bigmove":
        return (o - t.globex_open).abs() > 0.25 * f.atr
    if kind == "hivol":
        return f.atr > f.atr_med
    if kind == "lovol":
        return f.atr <= f.atr_med
    if kind == "trend":
        return np.sign(t.prev_close - f.ma20) == sig
    raise ValueError(kind)


def grid():
    specs = []
    for entry in range(9, 15):
        for exit_ in (12, 14, 16):
            if exit_ <= entry:
                continue
            for sig, mode, fl, sides, sm, tm in itertools.product(
                    ("globex", "prevclose", "o9", "gap", "prevday", "breakout", "long", "short"),
                    ("follow", "fade"), ("none", "bigmove", "hivol", "lovol", "trend"),
                    ("both", "long", "short"), (0, 0.25, 0.5, 1.0), (0, 0.5, 1.0)):
                if sig in ("long", "short") and (mode == "fade" or sides != "both"):
                    continue
                if sig == "o9" and entry == 9:
                    continue
                specs.append((entry, exit_, sig, mode, fl, sides, sm, tm))
    rng = np.random.default_rng(42)
    idx = rng.choice(len(specs), size=min(N_STRATEGIES, len(specs)), replace=False)
    return [specs[i] for i in sorted(idx)], len(specs)


def name(s):
    entry, exit_, sig, mode, fl, sides, sm, tm = s
    return f"{entry}h->{exit_}h {sig}/{mode} filt={fl} {sides} stop={sm}atr tgt={tm}atr"


# ---------------------------------------------------------------- evaluation
class Book:
    """Caches per-(entry, exit, side, stop, target) outcomes for one dataset."""

    def __init__(self, t, f):
        self.t, self.f, self.cache = t, f, {}
        big = np.full(len(t), 1e9)
        self.atr = f.atr.to_numpy()
        self.big = big

    def leg(self, entry, exit_, side, sm, tm):
        key = (entry, exit_, side, sm, tm)
        if key not in self.cache:
            stop = self.atr * sm if sm else self.big
            tgt = self.atr * tm if tm else self.big
            self.cache[key] = outcome(self.t, entry, exit_, side, stop, tgt)
        return self.cache[key]


def daily_dollars(book, spec, sides_override=None):
    """$ P&L per day using risk-based size, plus worst open loss $ and the signal used."""
    t, f = book.t, book.f
    entry, exit_, sig_kind, mode, fl, sides, sm, tm = spec
    sig = signal(t, f, sig_kind, entry)
    s = sig * (1 if mode == "follow" else -1)
    s = s.where(filt(t, f, fl, entry, s), 0)
    if sides == "long":
        s = s.clip(lower=0)
    elif sides == "short":
        s = s.clip(upper=0)
    s = s.fillna(0).to_numpy(dtype=float).copy()
    s[np.isnan(book.atr)] = 0
    if sides_override is not None:
        s = np.where(s != 0, sides_override, 0)
    pl_long, w_long = book.leg(entry, exit_, 1, sm, tm)
    pl_short, w_short = book.leg(entry, exit_, -1, sm, tm)
    pts = np.where(s > 0, pl_long, np.where(s < 0, pl_short, 0.0))
    worst = np.where(s > 0, w_long, np.where(s < 0, w_short, 0.0))
    if sm:
        qty = np.clip(np.floor(RISK_DOLLARS / (book.atr * sm * PT_VALUE + 2 * COST_PTS)), 1, 40)
    else:
        qty = np.full(len(t), NO_STOP_QTY)
    traded = s != 0
    dollars = np.where(traded, (pts - COST_PTS) * PT_VALUE * qty, 0.0)
    worst_d = np.where(traded, (worst + COST_PTS) * PT_VALUE * qty, 0.0)
    return dollars, worst_d, s


def metrics(d):
    tr = d[d != 0]
    if len(tr) < 2 or d.std() == 0:
        return dict(trades=len(tr), per_trade=0.0, total=0.0, sharpe=0.0, pf=0.0, max_dd=0.0)
    eq = np.cumsum(d)
    loss = -tr[tr < 0].sum()
    return dict(trades=len(tr), per_trade=tr.mean(), total=d.sum(), sharpe=d.mean() / d.std() * np.sqrt(252),
                pf=tr[tr > 0].sum() / loss if loss else np.inf, max_dd=(np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())


def prop_pass(d, w):
    n, res = len(d), []
    for st in range(n):
        bal = peak = 0.0
        out = None
        for i in range(st, min(n, st + RULES["max_days"])):
            if bal - min(w[i], RULES["dll"]) <= peak - RULES["dd"]:
                out = 0
                break
            bal += max(d[i], -RULES["dll"])
            if bal <= peak - RULES["dd"]:
                out = 0
                break
            peak = max(peak, bal)
            if bal >= RULES["target"]:
                out = 1
                break
        if out is None and st + RULES["max_days"] > n:
            continue
        res.append(out or 0)
    return float(np.mean(res)) if res else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    if args.refresh:
        refresh()
    table = build_day_table(load_days())
    feats = features(table)
    split = int(len(table) * TRAIN_FRAC)
    tr_t, te_t = table.iloc[:split].reset_index(drop=True), table.iloc[split:].reset_index(drop=True)
    tr_f, te_f = feats.iloc[:split].reset_index(drop=True), feats.iloc[split:].reset_index(drop=True)
    btr, bte = Book(tr_t, tr_f), Book(te_t, te_f)
    specs, total_space = grid()
    print(f"{len(table)} sessions | train {tr_t.session.iloc[0]}..{tr_t.session.iloc[-1]} "
          f"| test {te_t.session.iloc[0]}..{te_t.session.iloc[-1]}")
    print(f"testing {len(specs):,} strategies (sampled from {total_space:,}); "
          f"risk ${RISK_DOLLARS:,.0f}/trade with a stop, {NO_STOP_QTY} MNQ without\n")

    rng = np.random.default_rng(7)
    rows, rand_sharpes = [], []
    thirds = np.array_split(np.arange(len(tr_t)), 3)
    for spec in specs:
        d_tr, _, s_tr = daily_dollars(btr, spec)
        d_te, _, _ = daily_dollars(bte, spec)
        m_tr, m_te = metrics(d_tr), metrics(d_te)
        consistent = all(d_tr[idx].sum() > 0 for idx in thirds)
        # luck baseline: same trade days, random direction
        rs = rng.choice((-1, 1), size=len(tr_t))
        d_rand, _, _ = daily_dollars(btr, spec, sides_override=rs)
        rand_sharpes.append(metrics(d_rand)["sharpe"] if (d_rand != 0).sum() >= 100 else np.nan)
        rows.append(dict(strategy=name(spec), spec=spec, consistent=consistent,
                         **{f"train_{k}": v for k, v in m_tr.items()},
                         **{f"test_{k}": v for k, v in m_te.items()}))
    df = pd.DataFrame(rows)
    df.drop(columns="spec").to_csv(OUT, index=False, float_format="%.3f")
    ok = df[df.train_trades >= 100]
    rand_best = np.nanmax(rand_sharpes)

    print(f"Strategies with >=100 train trades: {len(ok):,}")
    print(f"Profitable after costs   train {(ok.train_total > 0).mean():.0%}   test {(ok.test_total > 0).mean():.0%}")
    print(f"Rank correlation train vs test Sharpe: {ok.train_sharpe.rank().corr(ok.test_sharpe.rank()):.2f}")
    print(f"Best TRAIN Sharpe, real strategies:   {ok.train_sharpe.max():.2f}")
    print(f"Best TRAIN Sharpe, random directions: {rand_best:.2f}   <- what pure luck reaches with 10,000 tries")
    beat_luck = ok[ok.train_sharpe > rand_best]
    print(f"Real strategies beating the luck line: {len(beat_luck)}  (of those, consistent in all 3 train thirds: "
          f"{beat_luck.consistent.sum()})\n")

    finalists = ok[ok.consistent].sort_values("train_sharpe", ascending=False).head(15).copy()
    print("Top 15 consistent strategies by TRAIN Sharpe, graded on unseen TEST (prop pass vs coin on TEST):")
    out = []
    for _, r in finalists.iterrows():
        d, w, s = daily_dollars(bte, r.spec)
        coin = np.mean([prop_pass(*daily_dollars(bte, r.spec, sides_override=np.random.default_rng(k).choice((-1, 1), len(s)))[:2])
                        for k in range(20)])
        out.append(dict(strategy=r.strategy, tr_sharpe=r.train_sharpe, tr_trade=r.train_per_trade,
                        te_sharpe=r.test_sharpe, te_trade=r.test_per_trade, te_total=r.test_total,
                        te_maxdd=r.test_max_dd, te_pass=prop_pass(d, w), te_coin=coin))
    out = pd.DataFrame(out)
    pd.set_option("display.width", 250)
    print(out.to_string(index=False, formatters={
        "tr_sharpe": "{:.2f}".format, "tr_trade": "${:,.0f}".format, "te_sharpe": "{:.2f}".format,
        "te_trade": "${:,.0f}".format, "te_total": "${:,.0f}".format, "te_maxdd": "${:,.0f}".format,
        "te_pass": "{:.0%}".format, "te_coin": "{:.0%}".format}))
    print(f"\nTop-15 median TEST Sharpe {out.te_sharpe.median():.2f}; profitable in TEST: {(out.te_total > 0).sum()}/15; "
          f"beat coin pass rate: {(out.te_pass > out.te_coin).sum()}/15")

    cur = (10, 16, "globex", "follow", "none", "both", 0, 0)
    d, w, s = daily_dollars(bte, cur)
    m = metrics(d)
    print(f"\nCurrent bot ({name(cur)}): TEST Sharpe {m['sharpe']:.2f}, ${m['per_trade']:,.0f}/trade, "
          f"total ${m['total']:,.0f}, pass {prop_pass(d, w):.0%}")


if __name__ == "__main__":
    main()
