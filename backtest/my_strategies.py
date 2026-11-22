"""Hand-designed NQ day-trading strategies, each with ONE fixed parameter set chosen
before testing (no tuning). Every strategy is flat by 16:00 ET and risks about $1,200
per trade (stop = fraction of the 20-day average 9:00-16:00 range, "ATR").

For each strategy:
  * results over the whole sample and in three equal time slices
  * a luck test: share of 500 random-direction versions (same days, same exits)
    that do at least as well - a p-value; with ~9 strategies, p < 0.01 is convincing
  * Tradeify 50K Growth pass rate vs coin flip

Strategies
  1 last_hour     Intraday momentum (Gao et al. 2018): if NQ is up from yesterday's close at
                  15:00, buy the last hour; if down, sell. Exit 16:00. Stop 0.25 ATR.
  2 orb           Opening-range breakout: if the 10:00 close is above the 9:00-10:00 high, buy
                  at 11:00 (below the low -> sell). Exit 16:00. Stop 0.5 ATR.
  3 trend_day     Trade with the 20-day trend: at 10:00 buy if yesterday closed above its 20-day
                  average and today is up since the Globex open (mirror for shorts). Exit 16:00.
  4 overnight_rev Mean reversion after an extreme night: if the 18:00->9:00 move exceeds 0.75 ATR,
                  fade it at 10:00. Exit 16:00. Stop 0.5 ATR.
  5 squeeze       Volatility squeeze: if yesterday's range was < 60% of ATR, trade a break of
                  yesterday's high/low seen at 11:00. Exit 16:00. Stop 0.5 ATR.
  6 turn_of_month Long bias around month turn: buy 10:00 on the last trading day and first 3
                  trading days of each month. Exit 16:00. Stop 0.5 ATR.
  7 afternoon_mom If 9:00->13:00 move exceeds 0.25 ATR, follow it 13:00->16:00. Stop 0.25 ATR.
  8 vote          Ensemble: at 10:00 take the majority of {globex momentum, 20-day trend,
                  prior-day direction}. Exit 16:00. Stop 0.5 ATR.
  0 current_bot   Reference: 10:00 follow the move since the Globex open, no ATR stop, 2 MNQ.

Usage: python3 backtest/my_strategies.py
"""
import numpy as np
import pandas as pd

import search10k as S
from daytrade import build_day_table, load_days

N_RANDOM = 500


def signals(t, f):
    """Each strategy -> (signal array of -1/0/1 per session, entry hour, exit hour, stop xATR, target xATR)."""
    atr = f.atr
    out = {}
    up_since_close = np.sign(t.o15 - t.prev_close)
    out["1_last_hour"] = (up_since_close, 15, 16, 0.25, 0)

    orb = np.where(t.c10 > t.h9, 1, np.where(t.c10 < t.l9, -1, 0))
    out["2_orb"] = (pd.Series(orb, index=t.index), 11, 16, 0.5, 0)

    trend = np.sign(t.prev_close - f.ma20)
    globex = np.sign(t.o10 - t.globex_open)
    out["3_trend_day"] = (trend.where(trend == globex, 0), 10, 16, 0.5, 0)

    night = t.o9 - t.globex_open
    out["4_overnight_rev"] = (pd.Series(np.where(night.abs() > 0.75 * atr, -np.sign(night), 0), index=t.index), 10, 16, 0.5, 0)

    prev_rng = f.prev_high - f.prev_low
    sq = prev_rng < 0.6 * atr
    brk = np.where(t.o11 > f.prev_high, 1, np.where(t.o11 < f.prev_low, -1, 0))
    out["5_squeeze"] = (pd.Series(np.where(sq, brk, 0), index=t.index), 11, 16, 0.5, 0)

    month = pd.to_datetime(t.session).dt.to_period("M")
    rank_fwd = month.groupby(month).cumcount()
    rank_bwd = month.groupby(month).cumcount(ascending=False)
    tom = (rank_fwd < 3) | (rank_bwd == 0)
    out["6_turn_of_month"] = (pd.Series(np.where(tom, 1, 0), index=t.index), 10, 16, 0.5, 0)

    am = t.o13 - t.o9
    out["7_afternoon_mom"] = (pd.Series(np.where(am.abs() > 0.25 * atr, np.sign(am), 0), index=t.index), 13, 16, 0.25, 0)

    votes = globex + trend.fillna(0) + f.prev_dir.fillna(0)
    out["8_vote"] = (np.sign(votes), 10, 16, 0.5, 0)

    out["0_current_bot"] = (globex, 10, 16, 0, 0)
    return out


def dollars(book, sig, entry, exit_, sm, tm):
    s = np.asarray(sig, dtype=float).copy()
    s[np.isnan(s) | np.isnan(book.atr)] = 0
    pl_l, w_l = book.leg(entry, exit_, 1, sm, tm)
    pl_s, w_s = book.leg(entry, exit_, -1, sm, tm)
    pts = np.where(s > 0, pl_l, np.where(s < 0, pl_s, 0.0))
    worst = np.where(s > 0, w_l, np.where(s < 0, w_s, 0.0))
    if sm:
        qty = np.clip(np.floor(S.RISK_DOLLARS / (book.atr * sm * S.PT_VALUE + 2 * S.COST_PTS)), 1, 40)
    else:
        qty = np.full(len(s), S.NO_STOP_QTY)
    qty = np.nan_to_num(qty, nan=1)
    traded = s != 0
    return (np.where(traded, (pts - S.COST_PTS) * S.PT_VALUE * qty, 0.0),
            np.where(traded, (worst + S.COST_PTS) * S.PT_VALUE * qty, 0.0), s)


def main():
    t = build_day_table(load_days()).reset_index(drop=True)
    f = S.features(t).reset_index(drop=True)
    book = S.Book(t, f)
    thirds = np.array_split(np.arange(len(t)), 3)
    labels = [f"{t.session.iloc[i[0]]:%Y-%m}..{t.session.iloc[i[-1]]:%Y-%m}" for i in thirds]
    print(f"{len(t)} sessions {t.session.iloc[0]} .. {t.session.iloc[-1]}  | slices: {', '.join(labels)}\n")
    rng = np.random.default_rng(2026)
    rows = []
    for name, (sig, e, x, sm, tm) in signals(t, f).items():
        d, w, s = dollars(book, sig, e, x, sm, tm)
        m = S.metrics(d)
        tr = d[d != 0]
        slices = [d[i].sum() for i in thirds]
        rand_sh, rand_pass = [], []
        for k in range(N_RANDOM):
            rs = np.where(s != 0, rng.choice((-1, 1), len(s)), 0)
            dr, wr, _ = dollars(book, rs, e, x, sm, tm)
            rand_sh.append(S.metrics(dr)["sharpe"])
            if k < 30:
                rand_pass.append(S.prop_pass(dr, wr))
        p = (np.sum(np.array(rand_sh) >= m["sharpe"]) + 1) / (N_RANDOM + 1)
        rows.append(dict(strategy=name, trades=m["trades"], win=(tr > 0).mean() if len(tr) else 0,
                         per_trade=m["per_trade"], total=m["total"], sharpe=m["sharpe"], max_dd=m["max_dd"],
                         s1=slices[0], s2=slices[1], s3=slices[2], p_luck=p,
                         pass_=S.prop_pass(d, w), coin=np.mean(rand_pass)))
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(df.to_string(index=False, formatters={
        "win": "{:.0%}".format, "per_trade": "${:,.0f}".format, "total": "${:,.0f}".format,
        "sharpe": "{:.2f}".format, "max_dd": "${:,.0f}".format, "s1": "${:,.0f}".format,
        "s2": "${:,.0f}".format, "s3": "${:,.0f}".format, "p_luck": "{:.3f}".format,
        "pass_": "{:.0%}".format, "coin": "{:.0%}".format}))
    df.to_csv(S.ROOT / "backtest" / "my_strategies_results.csv", index=False, float_format="%.3f")
    print("\np_luck = share of random-direction versions that did as well (lower is better; < 0.01 convincing with 9 tests)")
    print("s1/s2/s3 = profit in each third of the sample; pass_/coin = Tradeify 50K pass rate vs coin flip")


if __name__ == "__main__":
    main()
