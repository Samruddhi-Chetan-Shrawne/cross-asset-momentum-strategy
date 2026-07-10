"""
strategy.py — Core functions for the Cross-Asset Momentum Strategy (v8)

Reusable components extracted from CrossAssetStrategy_v8.ipynb.
Import these to use the strategy logic on any ETF universe or returns series.
"""

import numpy as np
import pandas as pd


# ============================================================
# PERFORMANCE METRICS
# ============================================================

def calc_metrics(returns: pd.Series, periods: int = 52) -> dict:
    """
    Compute standard performance metrics from a returns series.

    Parameters
    ----------
    returns : pd.Series
        Periodic returns (e.g. weekly). Should not include NaN.
    periods : int
        Number of periods per year. Default 52 (weekly).

    Returns
    -------
    dict with keys:
        Total Return, Ann. Return, Ann. Volatility, Sharpe,
        Sortino, Max Drawdown, Calmar, Win Rate
    """
    n = len(returns)
    total = (1 + returns).prod() - 1
    ann_ret = (1 + total) ** (periods / n) - 1
    ann_vol = returns.std() * np.sqrt(periods)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    cum = (1 + returns).cumprod()
    dd = (cum - cum.expanding().max()) / cum.expanding().max()
    max_dd = dd.min()
    calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

    win_rate = (returns > 0).mean()
    downside = returns[returns < 0].std() * np.sqrt(periods)
    sortino = ann_ret / downside if downside > 0 else 0

    return {
        "Total Return": total,
        "Ann. Return": ann_ret,
        "Ann. Volatility": ann_vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max Drawdown": max_dd,
        "Calmar": calmar,
        "Win Rate": win_rate,
    }


# ============================================================
# REGIME FILTER
# ============================================================

def get_regime_pct(
    weekly_prices: pd.DataFrame,
    signal_index: pd.Index,
    regime_full: float = 0.96,
    regime_caution: float = 0.94,
    regime_stress: float = 0.92,
    lookback: int = 4,
) -> pd.Series:
    """
    Compute the regime-adjusted deployment percentage for each week.

    Uses trailing returns of GLD and TLT as risk-off proxies:
      - Both positive  → FULL   (96% invested)
      - One negative   → CAUTION (94% invested)
      - Both negative  → STRESS  (92% invested)

    Parameters
    ----------
    weekly_prices : pd.DataFrame
        Weekly closing prices. Must include 'GLD' and 'TLT' columns.
    signal_index : pd.Index
        The dates for which to compute the regime (matches momentum.index).
    regime_full : float
        Deployment target when both GLD and TLT are positive.
    regime_caution : float
        Deployment target when one of GLD/TLT is negative.
    regime_stress : float
        Deployment target when both GLD and TLT are negative.
    lookback : int
        Number of weeks for trailing return. Default 4 (~1 month).

    Returns
    -------
    pd.Series indexed by signal_index with values in {regime_full, regime_caution, regime_stress}.
    """
    gld_trail = weekly_prices["GLD"].pct_change(lookback)
    tlt_trail = weekly_prices["TLT"].pct_change(lookback)

    regime_pct = pd.Series(regime_full, index=signal_index)

    for date in signal_index:
        gld_r = gld_trail.get(date, 0) or 0
        tlt_r = tlt_trail.get(date, 0) or 0
        if pd.isna(gld_r):
            gld_r = 0
        if pd.isna(tlt_r):
            tlt_r = 0

        neg_count = int((gld_r < 0) + (tlt_r < 0))
        if neg_count == 0:
            regime_pct[date] = regime_full
        elif neg_count == 1:
            regime_pct[date] = regime_caution
        else:
            regime_pct[date] = regime_stress

    return regime_pct


# ============================================================
# WEIGHT GENERATION
# ============================================================

def cap_weights(row: pd.Series, max_w: float = 0.25) -> pd.Series:
    """
    Apply a max single-asset weight cap and redistribute excess proportionally.

    Parameters
    ----------
    row : pd.Series
        One row of the weights DataFrame (one week's weights across all assets).
    max_w : float
        Maximum allowable weight for any single asset. Default 0.25.

    Returns
    -------
    pd.Series with weights clipped and excess redistributed.
    """
    capped = row.clip(upper=max_w)
    excess = row.sum() - capped.sum()
    uncapped_mask = capped < max_w
    if uncapped_mask.sum() > 0 and excess > 0:
        uncapped_total = capped[uncapped_mask].sum()
        if uncapped_total > 0:
            capped[uncapped_mask] += excess * (capped[uncapped_mask] / uncapped_total)
    return capped


def compute_weights(
    mom_rank: pd.DataFrame,
    ema_confirmed: pd.DataFrame,
    regime_pct: pd.Series,
    n_assets: int = 14,
    top_tier: int = 5,
    mult_strong: float = 1.3,
    mult_normal: float = 1.0,
    mult_weakening: float = 0.5,
    max_weight: float = 0.25,
    turnover_buffer: float = 0.02,
) -> pd.DataFrame:
    """
    Generate weekly portfolio weights using the three-tier signal system.

    Tiers:
      STRONG   (mult_strong)   — top N by momentum rank AND EMA confirmed
      NORMAL   (mult_normal)   — EMA confirmed but not top N
      WEAKENING (mult_weakening) — EMA broken (short-term trend reversed)

    After multipliers are applied, weights are:
      1. Renormalized to sum to 1
      2. Capped at max_weight per asset
      3. Scaled by regime_pct (deployment target)
      4. Shifted by 1 week (no lookahead)
      5. Filtered by turnover_buffer (no trade if change < buffer)

    Parameters
    ----------
    mom_rank : pd.DataFrame
        Momentum ranks (1 = worst, N = best) for each asset and week.
    ema_confirmed : pd.DataFrame
        Boolean DataFrame: True if EMA(short) > EMA(long) for that asset/week.
    regime_pct : pd.Series
        Deployment percentage per week from get_regime_pct().
    n_assets : int
        Total number of assets in the universe.
    top_tier : int
        Number of top-ranked assets eligible for STRONG classification.
    mult_strong : float
        Weight multiplier for STRONG assets.
    mult_normal : float
        Weight multiplier for NORMAL assets.
    mult_weakening : float
        Weight multiplier for WEAKENING assets.
    max_weight : float
        Maximum weight per asset after normalization.
    turnover_buffer : float
        Minimum weight change required to trigger a trade.

    Returns
    -------
    pd.DataFrame of final portfolio weights (dates × tickers), shifted and buffered.
    """
    tickers = mom_rank.columns.tolist()
    strong_threshold = n_assets - top_tier + 1  # e.g. 14 - 5 + 1 = 10

    # Base rank weights (rank / sum_of_ranks)
    rank_sums = mom_rank.sum(axis=1)
    base_weights = mom_rank.div(rank_sums, axis=0)

    # Apply tier multipliers
    multiplied = base_weights.copy()
    for date in mom_rank.index:
        for ticker in tickers:
            rank = mom_rank.loc[date].get(ticker, 0)
            ema_ok = ema_confirmed.loc[date].get(ticker, False)

            if pd.isna(rank):
                multiplied.loc[date, ticker] = base_weights.loc[date, ticker] * mult_weakening
                continue

            if rank >= strong_threshold and ema_ok:
                multiplied.loc[date, ticker] = base_weights.loc[date, ticker] * mult_strong
            elif ema_ok:
                multiplied.loc[date, ticker] = base_weights.loc[date, ticker] * mult_normal
            else:
                multiplied.loc[date, ticker] = base_weights.loc[date, ticker] * mult_weakening

    # Normalize → cap → apply regime
    mult_sums = multiplied.sum(axis=1)
    target_weights = multiplied.div(mult_sums, axis=0)
    target_weights = target_weights.apply(cap_weights, axis=1, max_w=max_weight)
    target_weights = target_weights.mul(regime_pct, axis=0)

    # Lag by 1 week (prevent lookahead)
    weights = target_weights.shift(1).dropna(how="all")

    # Turnover buffer
    buffered = weights.copy()
    for i in range(1, len(buffered)):
        prev = buffered.iloc[i - 1]
        curr = weights.iloc[i]
        delta = (curr - prev).abs()
        buffered.iloc[i] = np.where(delta < turnover_buffer, prev, curr)
        row_sum = buffered.iloc[i].sum()
        target_invest = regime_pct.iloc[i] if i < len(regime_pct) else 0.94
        if row_sum > 0:
            buffered.iloc[i] = buffered.iloc[i] / row_sum * target_invest

    return buffered
