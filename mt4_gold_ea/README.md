# MT4 GoldShortScalpEA

This folder contains a short-only MT4 Expert Advisor for XAUUSD short-term demo trading.

Important: this is a high-risk automated trading prototype, not financial advice. Test on a demo account first and run MT4 Strategy Tester before using real money.

## Files

- `Experts/GoldShortScalpEA.mq4`: MT4 Expert Advisor source code.
- `tests/test_gold_ea_rules.py`: lightweight source checks for the requested rule set.

## Model Implemented

- Symbol: `XAUUSD` by default.
- Starting account assumption: configurable broker account, designed around the user's 1000 USD / 100x leverage scenario.
- Max position size: `0.02` lot.
- Max open positions: `1`.
- Direction: short-only. The EA never sends buy orders.
- Entry filter: M5 bearish EMA cross plus RSI confirmation.
- Profit lock: once floating profit reaches a random `5-10` USD trigger, the EA moves stop loss to lock a random `5-10` USD profit.
- Fast profit exit: if floating profit reaches a random `10-20` USD threshold within `180` seconds, the EA closes immediately.
- Strict loss control: closes at `-8` USD floating loss, and sets an initial stop loss using the stricter of ATR distance and money-risk distance.
- Spread guard and cooldown are enabled.

## Local IC Markets MT4 Setup

1. Install and open IC Markets MT4 locally.
2. Log into your IC Markets demo account: `File` -> `Login to Trade Account`.
3. Open the MT4 data folder: `File` -> `Open Data Folder`.
4. Copy `Experts/GoldShortScalpEA.mq4` into `MQL4/Experts/`.
5. In MT4, open MetaEditor: press `F4`.
6. In MetaEditor, open `MQL4/Experts/GoldShortScalpEA.mq4`, then click `Compile`.
7. Return to MT4, right-click `Navigator` -> `Expert Advisors` -> `Refresh`.
8. Open Market Watch with `Ctrl+M`. If gold is not visible, right-click Market Watch -> `Show All`.
9. Find your broker's gold symbol. IC Markets commonly uses `XAUUSD`, but your demo server may show a suffix such as `XAUUSD.a` or `XAUUSDm`.
10. Open that gold chart and switch timeframe to `M5`.
11. Drag `GoldShortScalpEA` from `Navigator` -> `Expert Advisors` onto the chart.
12. On the `Common` tab, enable `Allow live trading`.
13. On the `Inputs` tab, set `TradeSymbol` to the exact chart symbol, for example `XAUUSD`.
14. Click `OK`, then turn on the main MT4 `AutoTrading` button.
15. Confirm the chart's top-right corner shows a smiling EA icon.
16. Watch `Terminal` -> `Experts` and `Journal` for errors.

## Suggested Demo Inputs

- `TradeSymbol`: exact IC Markets chart symbol, usually `XAUUSD`.
- `MaxLot`: `0.02`.
- `MaxOpenPositions`: `1`.
- `MaxSpreadPoints`: start with `80`; reduce only if trades are skipped too often.
- `MaxLossUSD`: start with `8.0`.
- `CooldownSeconds`: `90`.
- `SellRSIMax`: `48.0`; lower values mean fewer but stricter short entries.

## Strategy Tester

1. Press `Ctrl+R`.
2. Expert Advisor: `GoldShortScalpEA`.
3. Symbol: your IC Markets gold symbol.
4. Model: `Every tick`.
5. Period: `M5`.
6. Deposit: `1000`, leverage `1:100` if your tester build exposes leverage settings.
7. Enable `Visual mode` for the first run.
8. Run at least several weeks of data before leaving it live on the demo account.

## VPS Notes

Keep MT4 running on the VPS, logged into the broker account, with AutoTrading enabled. Disable Windows sleep and confirm the VPS clock is synchronized.
