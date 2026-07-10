# Cross-Asset Momentum Strategy (v8)

A rank-weighted, long-only momentum strategy across 14 ETFs spanning commodities, equity sectors, fixed income, and currencies. The core innovation is **continuous signal-based weight adjustments** — instead of discrete rebalancing, the portfolio reallocates weekly based on trend strength, following Man Group's "scale down, not just exit" principle.

Built and live-tested as part of FINTECH 543 (Quantitative Investment Analysis) at Duke University, Spring 2026.

---

## Strategy Overview

**Signal:** 12-minus-1 month momentum rank (52-week lookback, 4-week skip to avoid short-term reversal)

**Three-tier weight system:**

| Tier | Multiplier | Condition |
|------|-----------|-----------|
| STRONG | 1.3x | Top 5 by momentum rank AND EMA(10) > EMA(50) |
| NORMAL | 1.0x | EMA confirmed, not top 5 |
| WEAKENING | 0.5x | EMA(10) < EMA(50) — trend broken |

**Risk controls:**
- 25% maximum single-asset weight cap
- Graduated regime filter: 96% / 94% / 92% deployed based on GLD + TLT trailing returns
- 2% turnover buffer — no trade if weight change < 2 percentage points
- Weekly Friday-close signals, Monday morning execution

---

## Universe: 14 ETFs

| Asset Class | Tickers |
|------------|---------|
| Commodities | GLD, SLV, CPER, DBA |
| Equity Sectors | XLE, XLK, XLF |
| Fixed Income | TLT, LQD, HYG, TIP |
| Currencies | FXE, UUP, FXY |

---

## Results (2013–2026 Backtest)

| Metric | Strategy v8 | Equal-Weight | 60/40 SPY/AGG |
|--------|------------|-------------|---------------|
| Total Return | **+142.5%** | +106.1% | +234.6% |
| Sharpe Ratio | **0.79** | 0.71 | 0.94 |
| Sortino Ratio | **0.99** | 0.90 | 1.18 |
| Max Drawdown | **-13.1%** | -17.1% | -21.3% |
| Win Rate | **59.2%** | 56.7% | 59.3% |
| Momentum Spread | **+100.1%** | — | — |

> **Momentum spread** = Strategy return minus Inverse Momentum return. Proves the ranking signal has genuine predictive power.

### Sub-Period Robustness (4/5 periods won)

| Period | Strategy | Equal-Weight | Spread | Result |
|--------|----------|-------------|--------|--------|
| 2013-2015 | +4.00% | -9.64% | +13.64% | ✅ |
| 2016-2018 | +3.04% | +12.48% | -9.44% | ❌ |
| 2019-2021 | +46.68% | +39.64% | +7.03% | ✅ |
| 2022-2024 | +17.00% | +13.97% | +3.03% | ✅ |
| 2025-2026 | +31.88% | +27.42% | +4.47% | ✅ |

> 2016-2018 loss is consistent with the documented global momentum factor drawdown during that period.

### Ablation Test

| Variant | Sharpe | Max DD | vs Full v8 |
|---------|--------|--------|-----------|
| Full v8 (final) | **0.79** | -13.1% | — |
| No EMA filter | 0.85 | -15.6% | +0.06 Sharpe, -2.5% worse DD |
| No STRONG boost | 0.78 | -13.3% | -0.01 Sharpe |
| No regime filter | 0.78 | -12.5% | -0.01 Sharpe |
| Equal-weight baseline | 0.71 | -17.1% | -0.08 Sharpe |

> EMA filter is a **risk control** (lowers Sharpe slightly, improves drawdown by 2.5%). STRONG boost and regime filter each add modest positive Sharpe.

---

## Live Trading (4 Weeks, March–April 2026)

Executed on IBKR paper trading account. $1M account scaled 50x to $50M for reporting.

| Week | Period | TWRR | On $50M |
|------|--------|------|---------|
| 1 | Mar 23-27 | +0.47% | +$234K |
| 2 | Mar 30 - Apr 3 | +0.88% | +$446K |
| 3 | Apr 6-10 | +0.71% | +$355K |
| 4 | Apr 13-17 | +1.93% | +$965K |
| **Total** | **4 weeks** | **+4.06%** | **+$2,030K** |

Returns sourced from IBKR Time Weighted Rate of Return (TWRR).

---

## Repository Structure

```
cross-asset-momentum-strategy/
├── README.md
├── requirements.txt
├── .gitignore
├── notebooks/
│   └── CrossAssetStrategy_v8.ipynb   # Full strategy — runs top-to-bottom
├── src/
│   └── strategy.py                   # Reusable functions
└── results/
    ├── cumulative_returns.png         # Cumulative return chart vs benchmarks
    ├── weight_heatmap.png             # Portfolio weight evolution (last 52 weeks)
    └── performance_summary.csv        # Full metrics table
```

---

## Getting Started

```bash
git clone https://github.com/samruddhi-shrawne/cross-asset-momentum-strategy.git
cd cross-asset-momentum-strategy
pip install -r requirements.txt
jupyter notebook notebooks/CrossAssetStrategy_v8.ipynb
```

Run all cells top-to-bottom. The notebook downloads price data via `yfinance`, computes signals, generates weights, runs the backtest, and produces all charts and tables.

> **Note:** `weight_history_v8.csv` and `returns_history_v8.csv` are excluded from the repo (see `.gitignore`). Run the notebook locally to generate them. `results/performance_summary.csv` is included.

---

## Using `src/strategy.py`

Three reusable functions extracted from the notebook:

```python
from src.strategy import calc_metrics, get_regime_pct, compute_weights, cap_weights

# Compute performance metrics from any weekly returns series
metrics = calc_metrics(my_returns, periods=52)

# Get regime-adjusted deployment level each week
regime = get_regime_pct(weekly_prices, signal_index)

# Generate full weight DataFrame from ranks and EMA signals
weights = compute_weights(mom_rank, ema_confirmed, regime)
```

See docstrings in `src/strategy.py` for full parameter documentation.

---

## Research Foundation

- Jegadeesh & Titman (1993): momentum is persistent across 3-12 month horizons within equities
- Asness, Moskowitz & Pedersen (2013): momentum works across all asset classes simultaneously
- Moskowitz, Ooi & Pedersen (2012): time-series momentum in global futures markets

---

## Model Evolution

| Version | Change | Sharpe | Mom Spread |
|---------|--------|--------|-----------|
| v6 | Weekly rebalance, binary EMA (0.5x) | 0.77 | +81.6% |
| v7 | Concentrated 5-position with hard stops | 0.37 | — |
| **v8** | **Three-tier continuous scaling (1.3x/1.0x/0.5x)** | **0.79** | **+100.1%** |

The pivot from v6 to v8 was driven by professor feedback: "Rebalances don't work for momentum. Exits are an afterthought." The solution was to embed the exit into the weight multiplier itself — continuous scaling rather than discrete rebalancing.

---

## Author

**Samruddhi Shrawne**
Duke M.Eng. Financial Technology, Pratt School of Engineering
[LinkedIn](https://www.linkedin.com/in/samruddhi-shrawne-8a3787182/)
