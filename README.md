# Space Quant Lean

Quantitative trading strategies for the **publicly traded space sector** — built on the [QuantConnect LEAN](https://github.com/QuantConnect/Lean) engine. Each algorithm targets a specific space company, combining technical indicators with sector-specific catalysts like launch schedules, contract awards, and mission outcomes.

## Universe

Strategies are being developed for publicly traded space companies including:

| Ticker | Company | Focus |
|--------|---------|-------|
| **RKLB** | Rocket Lab | Launch events + swing trading |
| **LUNR** | Intuitive Machines | Lunar missions + NASA contracts |
| **ASTS** | AST SpaceMobile | Satellite launches + MNO partnerships |
| **PL** | Planet Labs | Satellite launches + gov contracts |
| **BKSY** | BlackSky Technology | Gen-3 launches + defense contracts |
| **RDW** | Redwire | NASA/DARPA contracts + ISS milestones |
| **MNTS** | Momentus | Vigoride launches + SDA contracts |
| SPCE | Virgin Galactic | *Planned* |
| BA | Boeing (space division) | *Planned* |
| LMT | Lockheed Martin (space) | *Planned* |
| NOC | Northrop Grumman (space) | *Planned* |

## Strategies

All strategies share the same architecture: 5 core technical indicators + company-specific event catalysts scored into a composite signal. A position is entered when the score reaches 3+.

### RKLB — Rocket Lab (7 signals)

Swing trades around Electron rocket launches. Buys pre-launch hype (1–5 days out) and post-successful-launch momentum. Stop loss 5%, take profit 10%. Backtest: Sep 2021 – Mar 2025.

### LUNR — Intuitive Machines (8 signals)

Swing trades around lunar mission milestones. Catalysts include IM-1/IM-2/IM-3 launches, lunar landings (huge volume events), and NASA CLPS contract awards. Wider stop loss at 7% due to higher volatility. Backtest: Mar 2023 – Jun 2025.

### ASTS — AST SpaceMobile (9 signals)

Swing trades around satellite deployment milestones. Catalysts include BlueBird satellite launches, MNO partnership announcements (AT&T, Vodafone, Google), FCC regulatory approvals, and technology firsts (first 5G from space). Widest stop at 8% for this high-beta name. Backtest: May 2021 – Jun 2025.

### PL — Planet Labs (8 signals)

Swing trades around Pelican/SuperDove satellite launches and government contract awards. Catalysts include NGA Luno B and NRO EOCL contract awards, large commercial Pelican deals, and earnings beats on revenue growth. Stop loss 6%, take profit 12%. Backtest: Feb 2022 – Jun 2025.

### BKSY — BlackSky Technology (8 signals)

Swing trades around Gen-2/Gen-3 satellite launches on Rocket Lab Electron and defense contract awards. Catalysts include NGA Luno B ($200M ceiling), multi-year international subscription contracts, Gen-3 first light milestones, and backlog growth. Stop loss 7%, take profit 13%. Backtest: Oct 2021 – Jun 2025.

### RDW — Redwire (8 signals)

Swing trades around NASA and DARPA contract awards and ISS technology milestones. Catalysts include FabLab in-space manufacturing, IROSA solar arrays, 3D bioprint heart tissue on ISS, DARPA SabreSat/Otter VLEO contracts, and backlog growth. Stop loss 7%, take profit 12%. Backtest: Nov 2021 – Jun 2025.

### MNTS — Momentus (8 signals)

Swing trades around Vigoride orbital transport launches on SpaceX Transporter missions and SDA contract wins. Catalysts include payload deployment successes, first $1M+ revenue quarter, SDA SBIR awards, and new customer contracts. Stop loss 8%, take profit 14%. Backtest: Oct 2021 – Jun 2025.

### Shared Risk Management

- **Trailing stop:** tightens to 3% floor once position is up 5%+
- **Time stop:** max 10 trading days per position
- **Max 5 trades/week**, max 1 open position at a time
- **95% of cash** per position (concentrated, small account)

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
│   │   ├── rklb_swing.py          # RKLB swing trading algorithm
│   │   ├── lunr_swing.py          # LUNR swing trading algorithm
│   │   └── asts_swing.py          # ASTS swing trading algorithm
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

- [x] RKLB swing strategy
- [x] LUNR swing strategy
- [x] ASTS swing strategy
- [x] PL swing strategy
- [x] BKSY swing strategy
- [x] RDW swing strategy
- [x] MNTS swing strategy
- [x] Auto data pipeline (ticker detection + download)
- [x] Interactive Flask dashboard
- [ ] Multi-ticker data pipeline for all space equities
- [ ] Sector-wide correlation / pairs trading
- [ ] NLP sentiment layer (earnings calls, launch press, social media)
- [ ] Portfolio-level strategy combining individual alpha signals

## License

This project is for personal research and educational purposes.
