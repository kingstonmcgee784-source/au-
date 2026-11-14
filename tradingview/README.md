# NQ Afternoon Momentum: TradingView → TradersPost → Tradeify (Tradovate)

One trade a day on MNQ.
- At **13:00 ET**, go long if price is above the 18:00 ET Globex open, or short if it is below.
- A protective stop is sent with the entry.
- The position is closed at **15:58 ET**, and a safety "exit" alert also goes out at **16:50 ET** (Tradeify requires you to be flat by 16:59 ET).

Defaults: **2 MNQ, 300-point stop, so at most $1,200 lost per trade.** That is under the
Tradeify 50K Growth daily loss limit of $1,250. The script stops with an error if
contracts × stop × $2 is more than the limit.

## Read this first

- **The edge is thin and unproven.** Backtested on hourly data, the rule beat a coin flip by about 10 percentage points
  in simulated evaluation pass rate. It lost money in 3 of 10 quarters, including the most recent
  60 days (−844 points, see `backtest/expected_trades.csv`). Expect losing stretches.
- **Tradeify's bot rules** (help center, "Guidelines for Traders"):
  - Bots are allowed if they are not high-frequency.
  - You must be the sole owner of the strategy.
  - You can't run the same strategy at other prop firms.
  - They can ask for a live video of you turning it on.
  - In funded accounts, more than 50% of trades must last over 10 seconds. These trades last hours.
- **Check your own dashboard's rules.** Firms change them. This was built against the 50K Growth plan: $3,000 target,
  $2,000 end-of-day trailing drawdown, $1,250 soft daily loss limit, max 4 NQ / 40 MNQ.

## Setup

1. **TradingView** (you need a paid plan for webhook alerts)
   - Open a `CME_MINI:MNQ1!` chart on 1-minute or 5-minute bars.
   - **Turn extended trading hours ON.** Without it the 18:00 Globex open is never seen, and the
     info table in the top right says so.
   - Open the Pine Editor, paste `nq_afternoon_momentum.pine`, then save and add it to the chart.
2. **Check the script against the Python version.** On a 5-minute chart, open Strategy Tester, then List of trades.
   Compare it with `backtest/expected_trades.csv`, which you can regenerate with `python3 backtest/pine_reference.py --refresh`.
   The dates and long/short directions should match. Prices can differ a little, because that file uses NQ data from Yahoo.
3. **TradersPost**
   - Connect a broker: choose Tradovate and log in with your **Tradeify** Tradovate credentials.
   - Create a strategy. Allow both long and short. Set the asset class to futures.
   - Subscribe it to your Tradeify account. **Start with the TradersPost paper account.**
   - Copy the strategy's webhook URL.
4. **TradingView alert**
   - Condition: *NQ Afternoon Momentum*, *Order fills and alert() function calls*.
   - Message: `{{strategy.order.alert_message}}` (nothing else).
   - Webhook URL: the TradersPost URL. Expiration: open-ended.
5. **Paper trade for 2–4 weeks.** Each day, check that the TradersPost fills match the Strategy Tester. Then switch
   the subscription from paper to your Tradeify account.

## Maintenance

- **Contract roll:** set the *TradersPost ticker* input to the front month, for example `MNQZ2026` until mid-December 2026
  and then `MNQH2027`. Change it on roll day and **re-create the alert**, because alerts keep the old settings.
- **Holidays and early closes:** add the dates to *Skip dates*. On an early-close day the market shuts at
  13:00 ET, exactly when the bot would enter.
- **If anything looks wrong,** disable the alert in TradingView and flatten in Tradovate by hand.

## Messages sent to TradersPost

```json
{"ticker":"MNQZ2026","action":"buy","sentiment":"bullish","quantity":2,"orderType":"market","signalPrice":28518.25,"stopLoss":{"type":"stop","stopPrice":28218.25}}
{"ticker":"MNQZ2026","action":"exit"}
```
