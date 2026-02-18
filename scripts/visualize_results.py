"""
Backtest Results Visualization Dashboard
Creates charts and HTML report from LEAN backtest results
"""
import json
import os
from datetime import datetime
import webbrowser

def load_results(results_dir):
    """Load all result files from the directory"""
    results = {}
    
    # Load main results JSON
    json_path = os.path.join(results_dir, "MyAlgorithm.json")
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            results['main'] = json.load(f)
    
    # Load summary JSON
    summary_path = os.path.join(results_dir, "MyAlgorithm-summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            results['summary'] = json.load(f)
    
    # Load log file
    log_path = os.path.join(results_dir, "MyAlgorithm-log.txt")
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            results['log'] = f.read()
    
    return results

def extract_equity_curve(results):
    """Extract equity curve data from results"""
    try:
        equity_data = results['summary']['charts']['Strategy Equity']['series']['Equity']['values']
        dates = []
        equity = []
        for point in equity_data:
            timestamp = point[0]
            # Convert Unix timestamp to datetime
            dt = datetime.fromtimestamp(timestamp)
            dates.append(dt.strftime('%Y-%m-%d'))
            equity.append(point[4])  # Close value
        return dates, equity
    except (KeyError, TypeError):
        return [], []

def extract_statistics(results):
    """Extract key statistics from results"""
    try:
        return results['summary']['statistics']
    except (KeyError, TypeError):
        return {}

def extract_orders(results):
    """Extract order information from results"""
    try:
        orders = results['main'].get('Orders', {})
        order_list = []
        for order_id, order in orders.items():
            order_list.append({
                'id': order_id,
                'symbol': order.get('Symbol', {}).get('Value', 'N/A'),
                'type': order.get('Type', 'N/A'),
                'quantity': order.get('Quantity', 0),
                'price': order.get('Price', 0),
                'time': order.get('Time', 'N/A'),
                'status': order.get('Status', 'N/A')
            })
        return order_list
    except (KeyError, TypeError):
        return []

def extract_trades(results):
    """Extract trade information from log"""
    trades = {'buys': 0, 'sells': 0, 'liquidations': 0}
    try:
        log = results.get('log', '')
        trades['buys'] = log.count('BUYING TSLA')
        trades['sells'] = log.count('SHORTING TSLA')
        trades['liquidations'] = log.count('LIQUIDATING')
    except:
        pass
    return trades

def generate_html_dashboard(results, output_path):
    """Generate an HTML dashboard from results"""
    
    stats = extract_statistics(results)
    dates, equity = extract_equity_curve(results)
    orders = extract_orders(results)
    trades = extract_trades(results)
    
    # Create equity chart data for Chart.js
    equity_labels = json.dumps(dates)
    equity_data = json.dumps(equity)
    
    # Calculate some derived stats
    start_equity = float(stats.get('Start Equity', 100000))
    end_equity = float(stats.get('End Equity', 100000))
    pnl = end_equity - start_equity
    pnl_pct = (pnl / start_equity) * 100 if start_equity > 0 else 0
    
    # Detect strategy name from stats
    algo_config = results.get('summary', {}).get('algorithmConfiguration', {})
    algo_name = algo_config.get('name', 'Strategy')
    start_dt = algo_config.get('startDate', '')[:10]
    end_dt = algo_config.get('endDate', '')[:10]
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Results - {start_dt} to {end_dt}</title>
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
            --border: #30363d;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
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
        
        .header .subtitle {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
        }}
        
        .stat-card .label {{
            color: var(--text-secondary);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.5rem;
        }}
        
        .stat-card .value {{
            font-size: 1.5rem;
            font-weight: bold;
        }}
        
        .stat-card .value.positive {{
            color: var(--accent-green);
        }}
        
        .stat-card .value.negative {{
            color: var(--accent-red);
        }}
        
        .chart-container {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .chart-container h2 {{
            color: var(--text-primary);
            font-size: 1.2rem;
            margin-bottom: 1rem;
        }}
        
        .orders-table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-card);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .orders-table th,
        .orders-table td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        .orders-table th {{
            background: var(--bg-secondary);
            color: var(--text-secondary);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .orders-table tr:hover {{
            background: var(--bg-secondary);
        }}
        
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
        }}
        
        .badge.buy {{
            background: rgba(63, 185, 80, 0.2);
            color: var(--accent-green);
        }}
        
        .badge.sell {{
            background: rgba(248, 81, 73, 0.2);
            color: var(--accent-red);
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }}
        
        .summary-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
        }}
        
        .summary-section h3 {{
            color: var(--accent-blue);
            margin-bottom: 1rem;
            font-size: 1rem;
        }}
        
        .summary-row {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border);
        }}
        
        .summary-row:last-child {{
            border-bottom: none;
        }}
        
        .summary-row .label {{
            color: var(--text-secondary);
        }}
        
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
        <h1>Backtest Results Dashboard</h1>
        <p class="subtitle">{start_dt} to {end_dt} | LEAN Engine | Start: ${start_equity:,.0f}</p>
    </div>
    
    <div class="grid">
        <div class="stat-card">
            <div class="label">Net Profit</div>
            <div class="value {'positive' if pnl >= 0 else 'negative'}">{stats.get('Net Profit', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Orders</div>
            <div class="value">{stats.get('Total Orders', '0')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Sharpe Ratio</div>
            <div class="value">{stats.get('Sharpe Ratio', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Max Drawdown</div>
            <div class="value negative">{stats.get('Drawdown', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Win Rate</div>
            <div class="value">{stats.get('Win Rate', 'N/A')}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Fees</div>
            <div class="value">{stats.get('Total Fees', '$0.00')}</div>
        </div>
    </div>
    
    <div class="chart-container">
        <h2>📊 Equity Curve</h2>
        <canvas id="equityChart" height="100"></canvas>
    </div>
    
    <div class="summary-grid">
        <div class="summary-section">
            <h3>💰 Performance Metrics</h3>
            <div class="summary-row">
                <span class="label">Start Equity</span>
                <span>${start_equity:,.2f}</span>
            </div>
            <div class="summary-row">
                <span class="label">End Equity</span>
                <span>${end_equity:,.2f}</span>
            </div>
            <div class="summary-row">
                <span class="label">P&L</span>
                <span class="{'positive' if pnl >= 0 else 'negative'}" style="color: {'var(--accent-green)' if pnl >= 0 else 'var(--accent-red)'}">${pnl:,.2f} ({pnl_pct:+.2f}%)</span>
            </div>
            <div class="summary-row">
                <span class="label">Compounding Annual Return</span>
                <span>{stats.get('Compounding Annual Return', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Sortino Ratio</span>
                <span>{stats.get('Sortino Ratio', 'N/A')}</span>
            </div>
        </div>
        
        <div class="summary-section">
            <h3>📈 Trade Statistics</h3>
            <div class="summary-row">
                <span class="label">Average Win</span>
                <span>{stats.get('Average Win', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Average Loss</span>
                <span>{stats.get('Average Loss', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Profit-Loss Ratio</span>
                <span>{stats.get('Profit-Loss Ratio', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Buy Signals</span>
                <span class="badge buy">{trades['buys']}</span>
            </div>
            <div class="summary-row">
                <span class="label">Short Signals</span>
                <span class="badge sell">{trades['sells']}</span>
            </div>
        </div>
        
        <div class="summary-section">
            <h3>⚙️ Risk Metrics</h3>
            <div class="summary-row">
                <span class="label">Alpha</span>
                <span>{stats.get('Alpha', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Beta</span>
                <span>{stats.get('Beta', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Annual Std Dev</span>
                <span>{stats.get('Annual Standard Deviation', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Treynor Ratio</span>
                <span>{stats.get('Treynor Ratio', 'N/A')}</span>
            </div>
            <div class="summary-row">
                <span class="label">Information Ratio</span>
                <span>{stats.get('Information Ratio', 'N/A')}</span>
            </div>
        </div>
    </div>
    
    <footer>
        <p>Generated by QuantConnect LEAN Engine Visualization Dashboard</p>
        <p>{start_dt} to {end_dt} | Total Orders: {stats.get('Total Orders', '0')} | Fees: {stats.get('Total Fees', '$0')}</p>
    </footer>
    
    <script>
        const ctx = document.getElementById('equityChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {equity_labels},
                datasets: [{{
                    label: 'Portfolio Equity',
                    data: {equity_data},
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{
                            color: '#30363d'
                        }},
                        ticks: {{
                            color: '#8b949e',
                            maxTicksLimit: 10
                        }}
                    }},
                    y: {{
                        grid: {{
                            color: '#30363d'
                        }},
                        ticks: {{
                            color: '#8b949e',
                            callback: function(value) {{
                                return '$' + value.toLocaleString();
                            }}
                        }}
                    }}
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
    import sys
    
    # Check command line args for which strategy to visualize
    if len(sys.argv) > 1:
        strategy = sys.argv[1]
    else:
        strategy = "space_strategy"  # Default to latest
    
    results_dirs = {
        "lesson9": "/Users/kfinney89/Documents/QuantConnect/Results/lesson9",
        "space_strategy": "/Users/kfinney89/Documents/QuantConnect/Results/space_strategy",
    }
    
    results_dir = results_dirs.get(strategy, strategy)
    
    if not os.path.exists(results_dir):
        print(f"Results directory not found: {results_dir}")
        print("Run the backtest first, then run this script.")
        return
    
    # Find the correct filename prefix (MyAlgorithm or RKLBSwingStrategy etc)
    json_files = [f for f in os.listdir(results_dir) if f.endswith('-summary.json')]
    if json_files:
        algo_name = json_files[0].replace('-summary.json', '')
    else:
        algo_name = "MyAlgorithm"
    
    print(f"Loading backtest results for: {algo_name}")
    results = load_results_flexible(results_dir, algo_name)
    
    if not results:
        print("No results found!")
        return
    
    # Generate HTML dashboard
    output_path = os.path.join(results_dir, "dashboard.html")
    generate_html_dashboard(results, output_path)
    
    print(f"\n✅ Dashboard generated: {output_path}")
    print("\nOpening in browser...")
    webbrowser.open(f"file://{output_path}")


def load_results_flexible(results_dir, algo_name):
    """Load result files with flexible algorithm name"""
    results = {}
    
    json_path = os.path.join(results_dir, f"{algo_name}.json")
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            results['main'] = json.load(f)
    
    summary_path = os.path.join(results_dir, f"{algo_name}-summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            results['summary'] = json.load(f)
    
    log_path = os.path.join(results_dir, f"{algo_name}-log.txt")
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            results['log'] = f.read()
    
    return results

if __name__ == "__main__":
    main()
