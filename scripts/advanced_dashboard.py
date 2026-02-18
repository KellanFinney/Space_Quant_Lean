"""
Advanced Backtest Analysis Dashboard
Generates comprehensive HTML report with:
1. Trade-by-Trade Breakdown
2. Monthly Returns Heatmap
3. Drawdown Chart
4. Buy & Hold Comparison
5. Signal Effectiveness Analysis
6. Win/Loss Distribution
7. Trade Timing / Launch Event Analysis
8. Rolling Performance
"""
import json
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
import webbrowser
import sys


def load_results(results_dir, algo_name=None):
    """Load all result files"""
    results = {}
    
    if not algo_name:
        json_files = [f for f in os.listdir(results_dir) if f.endswith('-summary.json')]
        algo_name = json_files[0].replace('-summary.json', '') if json_files else "MyAlgorithm"
    
    for suffix in ['', '-summary', '-log']:
        ext = '.json' if suffix != '-log' else '.txt'
        path = os.path.join(results_dir, f"{algo_name}{suffix}{ext}")
        if os.path.exists(path):
            if ext == '.json':
                with open(path, 'r') as f:
                    key = 'summary' if 'summary' in suffix else 'main'
                    results[key] = json.load(f)
            else:
                with open(path, 'r') as f:
                    results['log'] = f.read()
    
    return results, algo_name


def parse_trades_from_log(log_text):
    """Parse trade entries and exits from log text"""
    trades = []
    current_trade = None
    
    for line in log_text.split('\n'):
        # Parse BUY entries
        buy_match = re.search(r'(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2} BUY (\d+) RKLB @ \$([0-9.]+) \| Signal: (\d+) \| RSI: ([0-9.]+) \| MACD: ([0-9.-]+)', line)
        if buy_match:
            current_trade = {
                'entry_date': buy_match.group(1),
                'shares': int(buy_match.group(2)),
                'entry_price': float(buy_match.group(3)),
                'signal_score': int(buy_match.group(4)),
                'rsi': float(buy_match.group(5)),
                'macd': float(buy_match.group(6)),
            }
            continue
        
        # Parse SIGNAL SCORE for reasons
        signal_match = re.search(r'SIGNAL SCORE: \d+/7 \| (.+)', line)
        if signal_match and current_trade and 'signals' not in current_trade:
            current_trade['signals'] = signal_match.group(1).split(' | ')
        
        # Parse exits
        exit_match = re.search(r'(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2} (STOP LOSS|TAKE PROFIT|TIME STOP|TRAILING STOP): Sold RKLB @ \$([0-9.]+) \| P&L: ([0-9.-]+)% \| Held (\d+) days', line)
        if exit_match and current_trade:
            current_trade['exit_date'] = exit_match.group(1)
            current_trade['exit_type'] = exit_match.group(2)
            current_trade['exit_price'] = float(exit_match.group(3))
            current_trade['pnl_pct'] = float(exit_match.group(4))
            current_trade['hold_days'] = int(exit_match.group(5))
            current_trade['pnl_dollar'] = (current_trade['exit_price'] - current_trade['entry_price']) * current_trade['shares']
            current_trade['won'] = current_trade['pnl_pct'] > 0
            trades.append(current_trade)
            current_trade = None
    
    return trades


def parse_launch_events(log_text):
    """Parse launch events from log"""
    launches = []
    for line in log_text.split('\n'):
        match = re.search(r'(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2} LAUNCH EVENT: (.+) - (Success|Failure)', line)
        if match:
            launches.append({
                'date': match.group(1),
                'mission': match.group(2),
                'outcome': match.group(3)
            })
    return launches


def extract_equity_curve(results):
    """Extract equity curve from results"""
    try:
        values = results['summary']['charts']['Strategy Equity']['series']['Equity']['values']
        dates = []
        equity = []
        for point in values:
            dt = datetime.fromtimestamp(point[0])
            dates.append(dt.strftime('%Y-%m-%d'))
            equity.append(point[4])  # Close
        return dates, equity
    except (KeyError, TypeError):
        return [], []


def compute_drawdown(equity_values):
    """Compute drawdown series from equity curve"""
    peak = equity_values[0]
    drawdowns = []
    for val in equity_values:
        if val > peak:
            peak = val
        dd = ((val - peak) / peak) * 100 if peak > 0 else 0
        drawdowns.append(round(dd, 2))
    return drawdowns


def compute_monthly_returns(trades):
    """Compute monthly return aggregates"""
    monthly = defaultdict(float)
    for t in trades:
        month_key = t['entry_date'][:7]  # YYYY-MM
        monthly[month_key] += t['pnl_dollar']
    return dict(sorted(monthly.items()))


def compute_signal_effectiveness(trades):
    """Analyze which signals appear in winning vs losing trades"""
    signal_wins = defaultdict(int)
    signal_losses = defaultdict(int)
    signal_total = defaultdict(int)
    
    signal_names = [
        'RSI oversold recovery',
        'MACD bullish',
        'SMA uptrend',
        'Price above SMA20',
        'Near Bollinger lower band',
        'Launch in',
        'Post-launch momentum'
    ]
    
    for t in trades:
        for sig in t.get('signals', []):
            for name in signal_names:
                if name in sig:
                    signal_total[name] += 1
                    if t['won']:
                        signal_wins[name] += 1
                    else:
                        signal_losses[name] += 1
                    break
    
    effectiveness = {}
    for name in signal_names:
        total = signal_total.get(name, 0)
        wins = signal_wins.get(name, 0)
        if total > 0:
            effectiveness[name] = {
                'total': total,
                'wins': wins,
                'losses': signal_losses.get(name, 0),
                'win_rate': round((wins / total) * 100, 1)
            }
    return effectiveness


def compute_launch_trade_performance(trades, launches):
    """How did trades near launch events perform?"""
    launch_dates = set(l['date'] for l in launches)
    launch_trades = []
    non_launch_trades = []
    
    for t in trades:
        is_launch_trade = False
        for sig in t.get('signals', []):
            if 'launch' in sig.lower() or 'Launch' in sig:
                is_launch_trade = True
                break
        
        if is_launch_trade:
            launch_trades.append(t)
        else:
            non_launch_trades.append(t)
    
    def avg_pnl(trade_list):
        if not trade_list:
            return 0
        return sum(t['pnl_pct'] for t in trade_list) / len(trade_list)
    
    def win_rate(trade_list):
        if not trade_list:
            return 0
        return sum(1 for t in trade_list if t['won']) / len(trade_list) * 100
    
    return {
        'launch': {'count': len(launch_trades), 'avg_pnl': round(avg_pnl(launch_trades), 2), 'win_rate': round(win_rate(launch_trades), 1)},
        'non_launch': {'count': len(non_launch_trades), 'avg_pnl': round(avg_pnl(non_launch_trades), 2), 'win_rate': round(win_rate(non_launch_trades), 1)}
    }


def generate_advanced_dashboard(results, trades, launches, output_path):
    """Generate comprehensive HTML dashboard"""
    
    stats = results.get('summary', {}).get('statistics', {})
    trade_stats = results.get('summary', {}).get('totalPerformance', {}).get('tradeStatistics', {})
    algo_config = results.get('summary', {}).get('algorithmConfiguration', {})
    
    dates, equity = extract_equity_curve(results)
    drawdowns = compute_drawdown(equity)
    monthly_returns = compute_monthly_returns(trades)
    signal_eff = compute_signal_effectiveness(trades)
    launch_perf = compute_launch_trade_performance(trades, launches)
    
    start_equity = float(stats.get('Start Equity', 1000))
    end_equity = float(stats.get('End Equity', 1000))
    
    # Buy & Hold comparison: first trade entry to last trade exit
    if trades:
        bh_start = trades[0]['entry_price']
        bh_end = trades[-1].get('exit_price', trades[-1]['entry_price'])
        bh_return = ((bh_end - bh_start) / bh_start) * 100
        # Simulate buy & hold equity curve (scaled to start equity)
        bh_shares = start_equity / bh_start
    else:
        bh_return = 0
        bh_shares = 0
    
    # Trade P&L distribution buckets
    pnl_buckets = defaultdict(int)
    for t in trades:
        bucket = int(t['pnl_pct'] / 5) * 5  # Round to nearest 5%
        pnl_buckets[bucket] += 1
    sorted_buckets = sorted(pnl_buckets.items())
    
    # Monthly returns for heatmap
    years = sorted(set(k[:4] for k in monthly_returns.keys()))
    months_list = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Build heatmap data
    heatmap_data = []
    for y in years:
        for m_idx in range(12):
            key = f"{y}-{m_idx+1:02d}"
            val = monthly_returns.get(key, 0)
            heatmap_data.append({'year': y, 'month': months_list[m_idx], 'value': round(val, 2)})
    
    # Signal effectiveness chart data
    sig_labels = json.dumps(list(signal_eff.keys()))
    sig_win_rates = json.dumps([v['win_rate'] for v in signal_eff.values()])
    sig_counts = json.dumps([v['total'] for v in signal_eff.values()])
    
    # Trade table rows
    trade_rows = ""
    for i, t in enumerate(trades):
        color = '#3fb950' if t['won'] else '#f85149'
        badge_class = 'buy' if t['won'] else 'sell'
        trade_rows += f"""
        <tr>
            <td>{i+1}</td>
            <td>{t['entry_date']}</td>
            <td>{t['exit_date']}</td>
            <td>${t['entry_price']:.2f}</td>
            <td>${t['exit_price']:.2f}</td>
            <td>{t['shares']}</td>
            <td style="color:{color}">{t['pnl_pct']:+.1f}%</td>
            <td style="color:{color}">${t['pnl_dollar']:+.2f}</td>
            <td>{t['hold_days']}d</td>
            <td><span class="badge {badge_class}">{t['exit_type']}</span></td>
            <td>{t['signal_score']}/7</td>
        </tr>"""
    
    # Exit type breakdown
    exit_types = defaultdict(lambda: {'count': 0, 'total_pnl': 0})
    for t in trades:
        exit_types[t['exit_type']]['count'] += 1
        exit_types[t['exit_type']]['total_pnl'] += t['pnl_pct']
    
    exit_type_labels = json.dumps(list(exit_types.keys()))
    exit_type_counts = json.dumps([v['count'] for v in exit_types.values()])
    exit_type_avg_pnl = json.dumps([round(v['total_pnl']/v['count'], 2) if v['count'] > 0 else 0 for v in exit_types.values()])
    
    # Rolling win rate (last 10 trades)
    rolling_wr = []
    rolling_labels = []
    for i in range(9, len(trades)):
        window = trades[i-9:i+1]
        wr = sum(1 for t in window if t['won']) / len(window) * 100
        rolling_wr.append(round(wr, 1))
        rolling_labels.append(trades[i]['exit_date'])
    
    start_dt = algo_config.get('startDate', '')[:10]
    end_dt = algo_config.get('endDate', '')[:10]
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Advanced Backtest Dashboard - RKLB</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-blue: #58a6ff;
            --accent-purple: #bc8cff;
            --accent-yellow: #d29922;
            --accent-orange: #f0883e;
            --border: #30363d;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 1.5rem;
        }}
        .header {{
            text-align: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        .header h1 {{
            font-size: 2rem;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        .header .subtitle {{ color: var(--text-secondary); font-size: 0.9rem; }}
        .section-title {{
            font-size: 1.3rem;
            color: var(--accent-blue);
            margin: 2rem 0 1rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.2rem;
            text-align: center;
        }}
        .stat-card .label {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.4rem;
        }}
        .stat-card .value {{ font-size: 1.4rem; font-weight: bold; }}
        .positive {{ color: var(--accent-green) !important; }}
        .negative {{ color: var(--accent-red) !important; }}
        .chart-container {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        .chart-container h3 {{ color: var(--text-primary); font-size: 1rem; margin-bottom: 1rem; }}
        .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
        @media (max-width: 900px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
        .trade-table-wrapper {{ overflow-x: auto; margin-bottom: 1.5rem; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-card);
            border-radius: 8px;
            overflow: hidden;
            font-size: 0.85rem;
        }}
        th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{
            background: var(--bg-secondary);
            color: var(--text-secondary);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            position: sticky;
            top: 0;
        }}
        tr:hover {{ background: var(--bg-secondary); }}
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: bold;
        }}
        .badge.buy {{ background: rgba(63, 185, 80, 0.2); color: var(--accent-green); }}
        .badge.sell {{ background: rgba(248, 81, 73, 0.2); color: var(--accent-red); }}
        .heatmap {{ display: grid; grid-template-columns: 60px repeat(12, 1fr); gap: 2px; margin: 1rem 0; }}
        .heatmap-cell {{
            padding: 0.5rem 0.3rem;
            text-align: center;
            font-size: 0.7rem;
            border-radius: 4px;
            font-weight: bold;
        }}
        .heatmap-header {{ color: var(--text-secondary); font-size: 0.7rem; padding: 0.3rem; text-align: center; }}
        .comparison-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            display: flex;
            justify-content: space-around;
            align-items: center;
            margin-bottom: 1.5rem;
        }}
        .comparison-item {{ text-align: center; }}
        .comparison-item .label {{ color: var(--text-secondary); font-size: 0.8rem; margin-bottom: 0.3rem; }}
        .comparison-item .value {{ font-size: 1.8rem; font-weight: bold; }}
        .vs {{ font-size: 1.5rem; color: var(--text-secondary); font-weight: bold; }}
        footer {{
            text-align: center;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            color: var(--text-secondary);
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>RKLB Swing Strategy - Advanced Analysis</h1>
        <p class="subtitle">{start_dt} to {end_dt} | Rocket Lab (RKLB) | Start: ${start_equity:,.0f}</p>
    </div>

    <!-- KEY METRICS -->
    <div class="grid">
        <div class="stat-card">
            <div class="label">Net Profit</div>
            <div class="value {"positive" if end_equity >= start_equity else "negative"}">{stats.get('Net Profit', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">End Equity</div>
            <div class="value">${end_equity:,.2f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Trades</div>
            <div class="value">{len(trades)}</div>
        </div>
        <div class="stat-card">
            <div class="label">Win Rate</div>
            <div class="value">{stats.get('Win Rate', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Avg Win</div>
            <div class="value positive">{stats.get('Average Win', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Avg Loss</div>
            <div class="value negative">{stats.get('Average Loss', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Sharpe Ratio</div>
            <div class="value">{stats.get('Sharpe Ratio', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Max Drawdown</div>
            <div class="value negative">{stats.get('Drawdown', 'N/A')}</div>
        </div>
    </div>

    <!-- BUY & HOLD COMPARISON -->
    <h2 class="section-title">Strategy vs Buy & Hold</h2>
    <div class="comparison-card">
        <div class="comparison-item">
            <div class="label">Strategy Return</div>
            <div class="value {"positive" if end_equity >= start_equity else "negative"}">{((end_equity - start_equity) / start_equity * 100):+.1f}%</div>
        </div>
        <div class="vs">VS</div>
        <div class="comparison-item">
            <div class="label">Buy & Hold RKLB</div>
            <div class="value {"positive" if bh_return >= 0 else "negative"}">{bh_return:+.1f}%</div>
        </div>
    </div>

    <!-- EQUITY CURVE + DRAWDOWN -->
    <div class="chart-row">
        <div class="chart-container">
            <h3>Equity Curve</h3>
            <canvas id="equityChart" height="140"></canvas>
        </div>
        <div class="chart-container">
            <h3>Drawdown (%)</h3>
            <canvas id="drawdownChart" height="140"></canvas>
        </div>
    </div>

    <!-- SIGNAL EFFECTIVENESS + EXIT TYPE -->
    <h2 class="section-title">Signal & Exit Analysis</h2>
    <div class="chart-row">
        <div class="chart-container">
            <h3>Signal Win Rate (%)</h3>
            <canvas id="signalChart" height="160"></canvas>
        </div>
        <div class="chart-container">
            <h3>Exit Type Distribution</h3>
            <canvas id="exitChart" height="160"></canvas>
        </div>
    </div>

    <!-- LAUNCH EVENT PERFORMANCE -->
    <h2 class="section-title">Launch Event Impact</h2>
    <div class="comparison-card">
        <div class="comparison-item">
            <div class="label">Launch-Related Trades</div>
            <div class="value">{launch_perf['launch']['count']}</div>
            <div style="color: var(--text-secondary); font-size: 0.8rem;">Avg P&L: <span class="{"positive" if launch_perf["launch"]["avg_pnl"] >= 0 else "negative"}">{launch_perf['launch']['avg_pnl']:+.1f}%</span> | Win Rate: {launch_perf['launch']['win_rate']:.0f}%</div>
        </div>
        <div class="vs">VS</div>
        <div class="comparison-item">
            <div class="label">Non-Launch Trades</div>
            <div class="value">{launch_perf['non_launch']['count']}</div>
            <div style="color: var(--text-secondary); font-size: 0.8rem;">Avg P&L: <span class="{"positive" if launch_perf["non_launch"]["avg_pnl"] >= 0 else "negative"}">{launch_perf['non_launch']['avg_pnl']:+.1f}%</span> | Win Rate: {launch_perf['non_launch']['win_rate']:.0f}%</div>
        </div>
    </div>

    <!-- WIN/LOSS DISTRIBUTION + ROLLING WIN RATE -->
    <div class="chart-row">
        <div class="chart-container">
            <h3>P&L Distribution (%)</h3>
            <canvas id="distChart" height="140"></canvas>
        </div>
        <div class="chart-container">
            <h3>Rolling Win Rate (10-Trade Window)</h3>
            <canvas id="rollingChart" height="140"></canvas>
        </div>
    </div>

    <!-- MONTHLY RETURNS HEATMAP -->
    <h2 class="section-title">Monthly Returns ($)</h2>
    <div class="chart-container">
        <div class="heatmap">
            <div class="heatmap-header"></div>
            {"".join(f'<div class="heatmap-header">{m}</div>' for m in months_list)}
            {"".join(
                f'<div class="heatmap-header" style="text-align:right">{y}</div>' +
                "".join(
                    f'<div class="heatmap-cell" style="background:{"rgba(63,185,80," + str(min(abs(monthly_returns.get(f"{y}-{mi+1:02d}", 0))/100, 0.8)) + ")" if monthly_returns.get(f"{y}-{mi+1:02d}", 0) >= 0 else "rgba(248,81,73," + str(min(abs(monthly_returns.get(f"{y}-{mi+1:02d}", 0))/100, 0.8)) + ")"}; color:{"var(--accent-green)" if monthly_returns.get(f"{y}-{mi+1:02d}", 0) >= 0 else "var(--accent-red)"}">${monthly_returns.get(f"{y}-{mi+1:02d}", 0):+.0f}</div>'
                    if monthly_returns.get(f"{y}-{mi+1:02d}") is not None and monthly_returns.get(f"{y}-{mi+1:02d}", 0) != 0
                    else f'<div class="heatmap-cell" style="background:var(--bg-secondary);color:var(--text-secondary)">-</div>'
                    for mi in range(12)
                )
                for y in years
            )}
        </div>
    </div>

    <!-- TRADE TABLE -->
    <h2 class="section-title">Trade-by-Trade Breakdown ({len(trades)} trades)</h2>
    <div class="trade-table-wrapper" style="max-height: 600px; overflow-y: auto;">
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Entry $</th>
                    <th>Exit $</th>
                    <th>Shares</th>
                    <th>P&L %</th>
                    <th>P&L $</th>
                    <th>Held</th>
                    <th>Exit Type</th>
                    <th>Signal</th>
                </tr>
            </thead>
            <tbody>
                {trade_rows}
            </tbody>
        </table>
    </div>

    <footer>
        <p>RKLB Swing Strategy Advanced Dashboard | LEAN Engine</p>
        <p>Total Fees: {stats.get('Total Fees', '$0')} | {len(launches)} Launch Events Tracked</p>
    </footer>

    <script>
        const chartDefaults = {{
            responsive: true,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ grid: {{ color: '#30363d' }}, ticks: {{ color: '#8b949e', maxTicksLimit: 8 }} }},
                y: {{ grid: {{ color: '#30363d' }}, ticks: {{ color: '#8b949e' }} }}
            }}
        }};

        // Equity Curve
        new Chart(document.getElementById('equityChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [{{
                    label: 'Portfolio',
                    data: {json.dumps(equity)},
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88,166,255,0.1)',
                    fill: true, tension: 0.1, pointRadius: 0, borderWidth: 2
                }}]
            }},
            options: {{ ...chartDefaults,
                scales: {{ ...chartDefaults.scales,
                    y: {{ ...chartDefaults.scales.y, ticks: {{ ...chartDefaults.scales.y.ticks, callback: v => '$' + v.toLocaleString() }} }}
                }}
            }}
        }});

        // Drawdown Chart
        new Chart(document.getElementById('drawdownChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [{{
                    data: {json.dumps(drawdowns)},
                    borderColor: '#f85149',
                    backgroundColor: 'rgba(248,81,73,0.2)',
                    fill: true, tension: 0.1, pointRadius: 0, borderWidth: 2
                }}]
            }},
            options: {{ ...chartDefaults,
                scales: {{ ...chartDefaults.scales,
                    y: {{ ...chartDefaults.scales.y, ticks: {{ ...chartDefaults.scales.y.ticks, callback: v => v + '%' }} }}
                }}
            }}
        }});

        // Signal Effectiveness
        new Chart(document.getElementById('signalChart'), {{
            type: 'bar',
            data: {{
                labels: {sig_labels},
                datasets: [{{
                    label: 'Win Rate %',
                    data: {sig_win_rates},
                    backgroundColor: {json.dumps([('#3fb950' if wr > 50 else '#f0883e' if wr > 40 else '#f85149') for wr in [v['win_rate'] for v in signal_eff.values()]])},
                    borderRadius: 4
                }}]
            }},
            options: {{
                ...chartDefaults,
                indexAxis: 'y',
                scales: {{
                    x: {{ ...chartDefaults.scales.x, max: 100, ticks: {{ ...chartDefaults.scales.x.ticks, callback: v => v + '%' }} }},
                    y: {{ ...chartDefaults.scales.y, ticks: {{ color: '#8b949e', font: {{ size: 10 }} }} }}
                }}
            }}
        }});

        // Exit Type Distribution
        new Chart(document.getElementById('exitChart'), {{
            type: 'doughnut',
            data: {{
                labels: {exit_type_labels},
                datasets: [{{
                    data: {exit_type_counts},
                    backgroundColor: ['#f85149', '#3fb950', '#d29922', '#bc8cff'],
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ color: '#8b949e', padding: 15 }} }}
                }}
            }}
        }});

        // P&L Distribution
        new Chart(document.getElementById('distChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps([f"{b}% to {b+5}%" for b, _ in sorted_buckets])},
                datasets: [{{
                    data: {json.dumps([c for _, c in sorted_buckets])},
                    backgroundColor: {json.dumps(['#3fb950' if b >= 0 else '#f85149' for b, _ in sorted_buckets])},
                    borderRadius: 4
                }}]
            }},
            options: chartDefaults
        }});

        // Rolling Win Rate
        new Chart(document.getElementById('rollingChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(rolling_labels)},
                datasets: [{{
                    data: {json.dumps(rolling_wr)},
                    borderColor: '#bc8cff',
                    backgroundColor: 'rgba(188,140,255,0.1)',
                    fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2
                }}, {{
                    data: {json.dumps([50] * len(rolling_wr))},
                    borderColor: '#8b949e',
                    borderDash: [5, 5],
                    pointRadius: 0, borderWidth: 1
                }}]
            }},
            options: {{ ...chartDefaults,
                scales: {{ ...chartDefaults.scales,
                    y: {{ ...chartDefaults.scales.y, min: 0, max: 100, ticks: {{ ...chartDefaults.scales.y.ticks, callback: v => v + '%' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>'''
    
    with open(output_path, 'w') as f:
        f.write(html)
    return output_path


def main():
    strategy = sys.argv[1] if len(sys.argv) > 1 else "space_strategy"
    
    results_dirs = {
        "lesson9": "/Users/kfinney89/Documents/QuantConnect/Results/lesson9",
        "space_strategy": "/Users/kfinney89/Documents/QuantConnect/Results/space_strategy",
    }
    results_dir = results_dirs.get(strategy, strategy)
    
    if not os.path.exists(results_dir):
        print(f"Results directory not found: {results_dir}")
        return
    
    print("Loading backtest results...")
    results, algo_name = load_results(results_dir)
    
    print(f"Parsing trade log for {algo_name}...")
    log = results.get('log', '')
    trades = parse_trades_from_log(log)
    launches = parse_launch_events(log)
    
    print(f"Found {len(trades)} trades and {len(launches)} launch events")
    
    output_path = os.path.join(results_dir, "advanced_dashboard.html")
    generate_advanced_dashboard(results, trades, launches, output_path)
    
    print(f"\nDashboard generated: {output_path}")
    print("Opening in browser...")
    webbrowser.open(f"file://{output_path}")


if __name__ == "__main__":
    main()
