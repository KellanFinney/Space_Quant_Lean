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
├── app.py                         # Flask dashboard server
├── templates/
│   └── dashboard.html             # Interactive dashboard UI
├── static/
│   ├── css/dashboard.css          # Dark theme styles
│   └── js/dashboard.js            # Plotly charts + interactivity
├── Algorithms/
│   ├── space_strategy/
│   │   └── rklb_swing.py          # RKLB swing trading algorithm
│   ├── lesson9.py                 # TSLA sentiment algorithm
│   └── lesson10.py                # SPY/BND SMA rotation algorithm
├── scripts/
│   ├── advanced_dashboard.py      # Static HTML analysis dashboard
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

## Running the Dashboard

The interactive dashboard is a Flask app that can view results and launch backtests from the browser.

```bash
source venv/bin/activate
python app.py
# Open http://localhost:5000
```

From the dashboard you can:
- Select any algorithm under `Algorithms/` and click **Run Backtest** to execute it via Docker
- Load any previous result set to view equity curves, daily performance, benchmark/SMA overlays, statistics, orders, and logs
- Toggle overlays (Benchmark, SMA) and switch time ranges (1m, 3m, 1y, All)

## Running a Backtest (CLI)

You can also run backtests directly from the command line:

```bash
docker run --rm \
  -v $(pwd)/Algorithms:/Lean/Algorithm \
  -v $(pwd)/Data:/Lean/Data \
  -v $(pwd)/Results:/Results \
  -v $(pwd)/config.json:/Lean/Launcher/bin/Debug/config.json \
  lean-custom
```

Results are written to `Results/<strategy>/`.

## Static Analysis Dashboard

For the RKLB strategy specifically, a detailed static HTML dashboard is also available:

```bash
python scripts/advanced_dashboard.py space_strategy
```

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
