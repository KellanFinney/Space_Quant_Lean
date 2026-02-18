# Space Quant Lean

Quantitative trading strategies for the **publicly traded space sector** — built on the [QuantConnect LEAN](https://github.com/QuantConnect/Lean) engine. Each algorithm targets a specific space company, combining technical indicators with sector-specific catalysts like launch schedules, contract awards, and mission outcomes.

## Universe

Strategies are being developed for publicly traded space companies including:

| Ticker | Company | Focus |
|--------|---------|-------|
| **RKLB** | Rocket Lab | Launch events + swing trading |
| LUNR | Intuitive Machines | *Planned* |
| ASTS | AST SpaceMobile | *Planned* |
| PL | Planet Labs | *Planned* |
| BKSY | BlackSky Technology | *Planned* |
| RDW | Redwire | *Planned* |
| MNTS | Momentus | *Planned* |
| SPCE | Virgin Galactic | *Planned* |
| BA | Boeing (space division) | *Planned* |
| LMT | Lockheed Martin (space) | *Planned* |
| NOC | Northrop Grumman (space) | *Planned* |

## Current Strategy: RKLB Swing

The first completed algorithm (`RKLBSwingStrategy`) is a long-only swing trading strategy. It scores each trading day on a 0–7 composite signal and enters a position when the score reaches 3 or above.

### Signal Components

| # | Signal | Source |
|---|--------|--------|
| 1 | RSI oversold recovery (30–45 range) | Technical |
| 2 | MACD bullish crossover | Technical |
| 3 | SMA golden cross (20-day > 50-day) | Technical |
| 4 | Price above 20-day SMA | Technical |
| 5 | Price near Bollinger lower band | Technical |
| 6 | Upcoming launch (1–5 days out) | Event |
| 7 | Post-successful-launch momentum (≤3 days) | Event |

### Risk Management

- **Stop loss:** 5%
- **Take profit:** 10%
- **Trailing stop:** tightens to 3% floor once position is up 5%+
- **Time stop:** max 10 trading days per position
- **Max 5 trades/week**, max 1 open position at a time

## Project Structure

```
Space_Quant_Lean/
├── Algorithms/
│   ├── space_strategy/
│   │   └── rklb_swing.py          # RKLB swing trading algorithm
│   └── lesson9.py                 # Introductory LEAN algorithm
├── scripts/
│   ├── advanced_dashboard.py      # HTML backtest analysis dashboard
│   ├── visualize_results.py       # Basic results visualization
│   ├── download_rklb_data.py      # Yahoo Finance → LEAN format converter
│   └── download_data.py           # General data download utilities
├── Learning/
│   └── PythonA_Z/
│       └── ElonMuskPreprocessingTweats.py  # Musk tweet NLP preprocessing
├── Dockerfile                     # LEAN engine + NLTK container
├── config.json                    # LEAN engine configuration
├── requirements.txt               # Python dependencies
└── .gitignore
```

## Prerequisites

- [Docker](https://www.docker.com/) (for running LEAN backtests)
- Python 3.10+
- A [QuantConnect](https://www.quantconnect.com/) account (optional, for cloud backtests)

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/KellanFinney/Space_Quant_Lean.git
   cd Space_Quant_Lean
   ```

2. **Install Python dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Download market data**
   ```bash
   python scripts/download_rklb_data.py
   ```

4. **Build the Docker image** (adds NLTK to the LEAN base image)
   ```bash
   docker build -t lean-custom .
   ```

## Running a Backtest

Run the RKLB swing strategy against historical data:

```bash
docker run --rm \
  -v $(pwd)/Algorithms:/Lean/Algorithm \
  -v $(pwd)/Data:/Lean/Data \
  -v $(pwd)/Results:/Results \
  -v $(pwd)/config.json:/Lean/Launcher/config.json \
  lean-custom
```

Results are written to `Results/space_strategy/`.

## Analyzing Results

Generate an interactive HTML dashboard from backtest output:

```bash
python scripts/advanced_dashboard.py space_strategy
```

The dashboard includes equity curves, drawdown charts, signal effectiveness breakdowns, launch event impact analysis, monthly return heatmaps, and a full trade-by-trade table.

## Roadmap

- [ ] RKLB swing strategy (complete)
- [ ] Multi-ticker data pipeline for all space equities
- [ ] LUNR strategy — lunar mission contract catalysts
- [ ] ASTS strategy — satellite deployment milestones
- [ ] Sector-wide correlation / pairs trading
- [ ] NLP sentiment layer (earnings calls, launch press, social media)
- [ ] Portfolio-level strategy combining individual alpha signals

## License

This project is for personal research and educational purposes.
