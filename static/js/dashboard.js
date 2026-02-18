/* =========================================================================
   Space Quant — Interactive Backtest Dashboard
   ========================================================================= */

let currentData = null;   // holds the loaded result set
let currentRange = "all"; // active time range
let pollTimer = null;

// ---- DOM refs ----
const algoSelect   = document.getElementById("algo-select");
const resultSelect = document.getElementById("result-select");
const runBtn       = document.getElementById("run-btn");
const loadBtn      = document.getElementById("load-btn");
const statusText   = document.getElementById("status-text");

// ---- Initialise ----
document.addEventListener("DOMContentLoaded", () => {
    fetchAlgorithms();
    fetchResultSets();
    initTabs();
    initRangeBtns();

    runBtn.addEventListener("click", runBacktest);
    loadBtn.addEventListener("click", loadSelectedResult);

    document.getElementById("toggle-equity").addEventListener("change", renderCharts);
    document.getElementById("toggle-daily-perf").addEventListener("change", renderCharts);
    document.getElementById("toggle-benchmark").addEventListener("change", renderCharts);
    document.getElementById("toggle-sma").addEventListener("change", renderCharts);
});


/* =========================================================================
   API calls
   ========================================================================= */

async function fetchAlgorithms() {
    try {
        const res = await fetch("/api/algorithms");
        const algos = await res.json();
        algoSelect.innerHTML = '<option value="">— Choose Algorithm —</option>';
        algos.forEach(a => {
            const opt = document.createElement("option");
            opt.value = a.path;
            opt.textContent = a.path;
            algoSelect.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to fetch algorithms", e);
    }
}

async function fetchResultSets() {
    try {
        const res = await fetch("/api/results");
        const sets = await res.json();
        resultSelect.innerHTML = '<option value="">— View Results —</option>';
        sets.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.folder;
            opt.textContent = `${s.folder} (${s.algorithm})`;
            resultSelect.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to fetch result sets", e);
    }
}

async function loadResults(strategy) {
    statusText.textContent = "Loading...";
    try {
        const res = await fetch(`/api/results/${strategy}`);
        if (!res.ok) throw new Error(await res.text());
        currentData = await res.json();
        statusText.textContent = `Loaded: ${currentData.algorithm}`;
        renderAll();
    } catch (e) {
        statusText.textContent = "Error loading results.";
        console.error(e);
    }
}

function loadSelectedResult() {
    const val = resultSelect.value;
    if (val) loadResults(val);
}


/* =========================================================================
   Backtest runner
   ========================================================================= */

async function runBacktest() {
    const algo = algoSelect.value;
    if (!algo) { statusText.textContent = "Select an algorithm first."; return; }

    runBtn.disabled = true;
    statusText.innerHTML = '<span class="spinner"></span> Running backtest...';

    try {
        const res = await fetch("/api/run-backtest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ algorithm: algo }),
        });
        const data = await res.json();
        if (data.error) { statusText.textContent = data.error; runBtn.disabled = false; return; }

        pollBacktest(data.job_id);
    } catch (e) {
        statusText.textContent = "Failed to start backtest.";
        runBtn.disabled = false;
        console.error(e);
    }
}

function pollBacktest(jobId) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
        try {
            const res = await fetch(`/api/backtest-status/${jobId}`);
            const job = await res.json();

            if (job.status === "downloading_data") {
                statusText.innerHTML = '<span class="spinner"></span> Downloading missing ticker data...';
                return;
            }

            if (job.status === "running") {
                statusText.innerHTML = '<span class="spinner"></span> Backtest running...';
                return;
            }

            clearInterval(pollTimer);
            pollTimer = null;
            runBtn.disabled = false;

            if (job.status === "completed") {
                statusText.textContent = "Backtest complete!";
                await fetchResultSets();
                if (job.result_folder) {
                    resultSelect.value = job.result_folder;
                    loadResults(job.result_folder);
                }
            } else {
                statusText.textContent = `Backtest ${job.status}.`;
            }
        } catch (e) {
            clearInterval(pollTimer);
            pollTimer = null;
            runBtn.disabled = false;
            statusText.textContent = "Lost connection to backtest.";
        }
    }, 2000);
}


/* =========================================================================
   Render everything
   ========================================================================= */

function renderAll() {
    if (!currentData) return;
    renderMetrics();
    renderCharts();
    renderStats();
    renderOrders();
    renderLogs();
}


/* =========================================================================
   Metrics bar
   ========================================================================= */

function renderMetrics() {
    const s = currentData.statistics || {};

    setMetric("m-psr",         s["Probabilistic Sharpe Ratio"] || s["PSR"] || "—");
    setMetric("m-unrealized",  s["Unrealized"] || "—");
    setMetric("m-fees",        s["Total Fees"] || "—", true);
    setMetric("m-net-profit",  s["Net Profit"] || "—");
    setMetric("m-return",      s["Compounding Annual Return"] || "—");
    setMetric("m-equity",      s["End Equity"] ? "$" + parseFloat(s["End Equity"]).toLocaleString(undefined, {minimumFractionDigits:2}) : "—");
    setMetric("m-holdings",    s["Holdings"] || "—");
    setMetric("m-volume",      s["Total Orders"] || "—");
    setMetric("m-capacity",    s["Estimated Strategy Capacity"] || "—");
}

function setMetric(id, value, forceNegative) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    el.className = "value";

    const str = String(value).replace(/[$%,]/g, "");
    const num = parseFloat(str);
    if (!isNaN(num)) {
        if (forceNegative && num !== 0) el.classList.add("negative");
        else if (num > 0) el.classList.add("positive");
        else if (num < 0) el.classList.add("negative");
    }
}


/* =========================================================================
   Charts (Plotly)
   ========================================================================= */

function renderCharts() {
    if (!currentData) return;

    const showEquity    = document.getElementById("toggle-equity").checked;
    const showDailyPerf = document.getElementById("toggle-daily-perf").checked;
    const showBenchmark = document.getElementById("toggle-benchmark").checked;
    const showSMA       = document.getElementById("toggle-sma").checked;

    // ----- Equity Chart -----
    const equityTraces = [];
    const eq = currentData.equity_curve || [];

    if (showEquity && eq.length) {
        const filtered = filterByRange(eq);
        equityTraces.push({
            x: filtered.map(p => p.date),
            y: filtered.map(p => p.value),
            type: "scatter",
            mode: "lines",
            name: "Equity",
            line: { color: "#58a6ff", width: 2 },
            fill: "tozeroy",
            fillcolor: "rgba(88,166,255,0.06)",
        });
    }

    if (showBenchmark) {
        const bm = filterByRange(currentData.benchmark_curve || []);
        if (bm.length) {
            equityTraces.push({
                x: bm.map(p => p.date),
                y: bm.map(p => p.value),
                type: "scatter",
                mode: "lines",
                name: "Benchmark",
                line: { color: "#d29922", width: 1.5, dash: "dot" },
                yaxis: "y2",
            });
        }
    }

    if (showSMA) {
        const custom = currentData.custom_charts || {};
        for (const [chartName, series] of Object.entries(custom)) {
            for (const [seriesName, points] of Object.entries(series)) {
                if (seriesName.toUpperCase().includes("SMA") || chartName.toUpperCase().includes("SMA") || chartName === "Benchmark") {
                    const filt = filterByRange(points);
                    if (filt.length) {
                        equityTraces.push({
                            x: filt.map(p => p.date),
                            y: filt.map(p => p.value),
                            type: "scatter",
                            mode: "lines",
                            name: `${chartName} — ${seriesName}`,
                            line: { color: "#bc8cff", width: 1.5 },
                            yaxis: "y2",
                        });
                    }
                }
            }
        }
    }

    const equityLayout = {
        paper_bgcolor: "#0d1117",
        plot_bgcolor: "#0d1117",
        margin: { l: 60, r: 60, t: 10, b: 30 },
        font: { color: "#8b949e", size: 11 },
        xaxis: {
            gridcolor: "#21262d",
            linecolor: "#30363d",
            tickformat: "%b '%y",
        },
        yaxis: {
            gridcolor: "#21262d",
            linecolor: "#30363d",
            tickprefix: "$",
            side: "left",
        },
        yaxis2: {
            overlaying: "y",
            side: "right",
            gridcolor: "transparent",
            linecolor: "#30363d",
        },
        legend: {
            orientation: "h",
            y: 1.12,
            font: { size: 10, color: "#8b949e" },
        },
        hovermode: "x unified",
    };

    Plotly.newPlot("equity-chart", equityTraces, equityLayout, {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"],
    });

    // ----- Daily Performance Bars -----
    const perfDiv = document.getElementById("daily-perf-chart");
    if (showDailyPerf) {
        perfDiv.style.display = "block";
        const dp = filterByRange(currentData.daily_performance || []);
        const perfTraces = [{
            x: dp.map(p => p.date),
            y: dp.map(p => p.value),
            type: "bar",
            marker: {
                color: dp.map(p => p.value >= 0 ? "#3fb950" : "#f85149"),
            },
            hovertemplate: "%{x}<br>%{y:.2f}%<extra></extra>",
        }];

        const perfLayout = {
            paper_bgcolor: "#0d1117",
            plot_bgcolor: "#0d1117",
            margin: { l: 60, r: 60, t: 0, b: 20 },
            font: { color: "#8b949e", size: 10 },
            xaxis: { gridcolor: "#21262d", linecolor: "#30363d", tickformat: "%b '%y" },
            yaxis: {
                gridcolor: "#21262d",
                linecolor: "#30363d",
                ticksuffix: "%",
                zeroline: true,
                zerolinecolor: "#30363d",
            },
            bargap: 0.3,
            showlegend: false,
            hovermode: "x unified",
        };

        Plotly.newPlot("daily-perf-chart", perfTraces, perfLayout, {
            responsive: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"],
        });
    } else {
        perfDiv.style.display = "none";
    }
}


/* =========================================================================
   Time range filter
   ========================================================================= */

function filterByRange(points) {
    if (!points.length || currentRange === "all") return points;

    const last = new Date(points[points.length - 1].date);
    let cutoff = new Date(last);

    switch (currentRange) {
        case "1m": cutoff.setMonth(cutoff.getMonth() - 1); break;
        case "3m": cutoff.setMonth(cutoff.getMonth() - 3); break;
        case "1y": cutoff.setFullYear(cutoff.getFullYear() - 1); break;
        default: return points;
    }

    return points.filter(p => new Date(p.date) >= cutoff);
}

function initRangeBtns() {
    document.querySelectorAll(".range-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".range-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentRange = btn.dataset.range;
            renderCharts();
        });
    });
}


/* =========================================================================
   Statistics table
   ========================================================================= */

const STAT_LAYOUT = [
    ["PSR",                            "Sharpe Ratio"],
    ["Total Trades",                   "Average Win"],
    ["Average Loss",                   "Compounding Annual Return"],
    ["Drawdown",                       "Expectancy"],
    ["Net Profit",                     "Probabilistic Sharpe Ratio"],
    ["Loss Rate",                      "Win Rate"],
    ["Profit-Loss Ratio",             "Alpha"],
    ["Beta",                           "Annual Standard Deviation"],
    ["Annual Variance",                "Information Ratio"],
    ["Tracking Error",                 "Treynor Ratio"],
    ["Total Fees",                     "Estimated Strategy Capacity"],
    ["Lowest Capacity Asset",          "Portfolio Turnover"],
];

function renderStats() {
    const grid = document.getElementById("stats-grid");
    grid.innerHTML = "";
    const s = currentData.statistics || {};

    STAT_LAYOUT.forEach(([left, right]) => {
        grid.appendChild(statRow(left, s[left]));
        grid.appendChild(statRow(right, s[right]));
    });
}

function statRow(label, value) {
    const div = document.createElement("div");
    div.className = "stat-row";
    div.innerHTML = `<span class="stat-label">${label}</span><span class="stat-value">${value ?? "—"}</span>`;
    return div;
}


/* =========================================================================
   Orders table
   ========================================================================= */

function renderOrders() {
    const tbody = document.getElementById("orders-body");
    tbody.innerHTML = "";

    const orders = currentData.orders || [];
    if (!orders.length) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-secondary)">No orders</td></tr>';
        return;
    }

    orders.forEach(o => {
        const dirClass = o.direction === "Buy" ? "buy" : "sell";
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${o.id}</td>
            <td>${formatTime(o.time)}</td>
            <td>${o.symbol}</td>
            <td>${o.type}</td>
            <td><span class="badge ${dirClass}">${o.direction}</span></td>
            <td>${Math.abs(o.quantity)}</td>
            <td>$${parseFloat(o.price).toFixed(2)}</td>
            <td>$${parseFloat(o.value).toLocaleString(undefined, {minimumFractionDigits:2})}</td>
            <td>${o.status}</td>
            <td>${o.tag || ""}</td>`;
        tbody.appendChild(tr);
    });
}

function formatTime(t) {
    if (!t) return "";
    return t.replace("T", " ").slice(0, 19);
}


/* =========================================================================
   Logs
   ========================================================================= */

function renderLogs() {
    const logEl = document.getElementById("log-output");
    logEl.textContent = currentData.log || "No log output.";
}


/* =========================================================================
   Tab switching
   ========================================================================= */

function initTabs() {
    document.querySelectorAll(".tab-bar .tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".tab-bar .tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            tab.classList.add("active");
            document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
        });
    });
}
