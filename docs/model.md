# Model Notes

The forecast engine combines team-strength metrics and contextual adjustments. Current confidence labels are heuristic. They should not be interpreted as betting guarantees.

Primary components:

- SRS and margin-based team strength
- Net-rating-style efficiency input
- Pythagorean regression input
- Recent form
- Home court
- Back-to-back/fatigue adjustments
- Head-to-head and matchup context

## Calibration requirement

Before using confidence labels as public claims, backtest against historical outcomes and measure:

- Brier score
- log loss
- calibration by probability bucket
- accuracy by confidence tier
- comparison against simple baselines

Backfilled history is marked separately because it is not equivalent to real-time tracked forecasts.
