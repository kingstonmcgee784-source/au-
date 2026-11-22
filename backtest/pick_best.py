"""Rank the 10,000 strategies from search10k.py by their WORSE period (min of train and test Sharpe),
compare with the same ranking on random-direction strategies, and grade the top pick under
Tradeify 50K rules. Usage: python3 backtest/pick_best.py
"""
import numpy as np, pandas as pd
import search10k as S
from daytrade import build_day_table, load_days, TRAIN_FRAC
t = build_day_table(load_days()); f = S.features(t); sp = int(len(t)*TRAIN_FRAC)
B = [S.Book(t.iloc[a:b].reset_index(drop=True), f.iloc[a:b].reset_index(drop=True)) for a,b in ((0,sp),(sp,len(t)))]
full = S.Book(t.reset_index(drop=True), f.reset_index(drop=True))
specs, _ = S.grid()
cur = (10, 16, "globex", "follow", "none", "both", 0, 0)
if cur not in specs: specs.append(cur)
rng = np.random.default_rng(11)
rows, rand = [], []
for s in specs:
    m = [S.metrics(S.daily_dollars(b, s)[0]) for b in B]
    if min(m[0]["trades"], m[1]["trades"]) < 80: continue
    rows.append(dict(spec=s, name=S.name(s), score=min(m[0]["sharpe"], m[1]["sharpe"]),
                     tr=m[0]["sharpe"], te=m[1]["sharpe"], tr_pt=m[0]["per_trade"], te_pt=m[1]["per_trade"]))
    rs = [S.metrics(S.daily_dollars(b, s, sides_override=rng.choice((-1,1), len(b.t)))[0])["sharpe"] for b in B]
    rand.append(min(rs))
df = pd.DataFrame(rows).sort_values("score", ascending=False)
print(f"{len(df)} strategies with >=80 trades in both periods")
print(f"best min(train,test) Sharpe: real {df.score.iloc[0]:.2f} | random-direction best {max(rand):.2f}, 99th pct {np.percentile(rand,99):.2f}")
top = df.head(10).copy()
out=[]
for _, r in top.iterrows():
    d, w, _ = S.daily_dollars(full, r.spec); m = S.metrics(d)
    d2, w2, _ = S.daily_dollars(B[1], r.spec)
    out.append(dict(name=r["name"], tr=r.tr, te=r.te, tr_pt=r.tr_pt, te_pt=r.te_pt, all_total=m["total"], all_dd=m["max_dd"],
                    trades=m["trades"], pass_all=S.prop_pass(d, w), pass_te=S.prop_pass(d2, w2)))
pd.set_option("display.width", 250)
print(pd.DataFrame(out).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
r = df[df.spec == cur].iloc[0]
print(f"\ncurrent bot rank {list(df.spec).index(cur)+1}/{len(df)}: train {r.tr:.2f} test {r.te:.2f}")
print(f"\nreal strategies with score > random 99th pct: {(df.score > np.percentile(rand,99)).sum()} (luck would give ~{0.01*len(df):.0f})")
best = df.spec.iloc[0]
for name, b in (("all", full), ("test", B[1])):
    d, w, _ = S.daily_dollars(b, best)
    coin = np.mean([S.prop_pass(*S.daily_dollars(b, best, sides_override=np.random.default_rng(k).choice((-1,1), len(b.t)))[:2]) for k in range(30)])
    q = np.clip(np.floor(S.RISK_DOLLARS / (b.atr * 0.25 * 2 + 3.5)), 1, 40)
    print(f"{name}: pass {S.prop_pass(d, w):.0%} vs coin {coin:.0%}; size median {np.nanmedian(q):.0f} MNQ")
