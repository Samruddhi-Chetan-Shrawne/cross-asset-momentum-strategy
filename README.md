# Cross-Asset Momentum Strategy

**Universe:** 14 ETFs across commodities, equity sectors, fixed income, FX  
**Backtest period:** 2010–2024  
**Final Sharpe:** 0.78  
**Deployed on:** Interactive Brokers paper account ($50M simulated)

## Research Question
Can rank-weighted momentum signals generate consistent risk-adjusted 
returns across asset classes with minimal correlation to any single sector?

## Methodology
- Trailing 12-month return ranking with EMA trend confirmation
- Three-tier signal weighting: STRONG (1.3x) / NORMAL (1.0x) / WEAKENING (0.5x)
- 25% single-asset concentration cap, 2% turnover buffer
- Graduated macro regime filter

## Key Results


## Iteration Log
This strategy went through 8 design versions. Notable changes:
- v1–v3: Fixed weekly rebalancing → failed; momentum signals require 
  longer holding periods


## Files
- `notebooks/momentum_backtest.ipynb` — full backtest with performance charts
- `src/strategy.py` — signal generation and weighting logic
