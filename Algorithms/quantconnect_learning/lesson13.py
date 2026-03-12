"""
Breakout call buy strategy with VIX filter.

Buys ATM calls when price breaks 1-month high. Uses VIX rank (local custom data)
to filter trades. Liquidates 4 days before expiration.

Uses local LEAN: custom VIX from Data/custom/vix_daily.csv (Date,Close format).
"""

from AlgorithmImports import *
from datetime import timedelta


class BreakoutCallBuy(QCAlgorithm):

    def Initialize(self):
        self.set_start_date(2017, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(100000)

        equity = self.AddEquity("MSFT", Resolution.Daily)
        equity.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.equity = equity.Symbol
        self.SetBenchmark(self.equity)

        # VIX from local custom CSV (QuantConnect CBOE not available locally)
        self.vix = self.AddData(VIXDaily, "VIXDAILY", Resolution.Daily).Symbol

        option = self.AddOption("MSFT", Resolution.Daily)
        option.SetFilter(-3, 3, timedelta(20), timedelta(40))

        self.high = self.MAX(self.equity, 21, Resolution.Daily, Field.High)

        self.rank = 0.5  # 0-1; VIX rank, default mid
        self.lookbackIV = 150

        self.Schedule.On(
            self.DateRules.EveryDay(self.equity),
            self.TimeRules.AfterMarketOpen(self.equity, 30),
            self.Plotting,
        )
        self.Schedule.On(
            self.DateRules.EveryDay(self.equity),
            self.TimeRules.BeforeMarketClose(self.equity, 30),
            self.VIXRank,
        )

        self.SetWarmUp(timedelta(days=max(self.lookbackIV, 21)))

    def Plotting(self):
        if self.high.IsReady and self.equity in self.Securities:
            self.Plot("Breakout", "High", self.high.Current.Value)
            self.Plot("Breakout", "Price", self.Securities[self.equity].Price)
            self.Plot("Breakout", "VIXRank", self.rank)

    def VIXRank(self):
        history = self.History(VIXDaily, self.vix, self.lookbackIV, Resolution.Daily)
        if history is None or history.empty or len(history) < self.lookbackIV // 2:
            return

        col = "value" if "value" in history.columns else history.columns[-1]
        vals = history[col]
        vmin, vmax = vals.min(), vals.max()
        if vmax <= vmin:
            self.rank = 0.5
        else:
            current = self.Securities[self.vix].Price
            self.rank = (current - vmin) / (vmax - vmin)

    def OnData(self, data):
        if self.IsWarmingUp:
            return
        if not self.high.IsReady:
            return

        option_invested = [
            x.Key for x in self.Portfolio if x.Value.Invested and x.Value.Type == SecurityType.Option
        ]

        if option_invested:
            if self.Time + timedelta(4) > option_invested[0].ID.Date:
                self.Liquidate(option_invested[0], "Too close to expiration")
            return

        if self.Securities[self.equity].Price >= self.high.Current.Value:
            for i in data.OptionChains:
                chains = i.Value
                self.BuyCall(chains)

    def BuyCall(self, chains):
        if chains is None or len(chains) == 0:
            return
        expiry = sorted(chains, key=lambda x: x.Expiry, reverse=True)[0].Expiry
        calls = [i for i in chains if i.Expiry == expiry and i.Right == OptionsRight.Call]
        call_contracts = sorted(calls, key=lambda x: abs(x.Strike - x.UnderlyingLastPrice))
        if len(call_contracts) == 0:
            return
        self.call = call_contracts[0]

        quantity = self.Portfolio.TotalPortfolioValue / self.call.AskPrice
        quantity = int(0.05 * quantity / 100)
        if quantity > 0:
            self.Buy(self.call.Symbol, quantity)

    def OnOrderEvent(self, orderEvent):
        order = self.Transactions.GetOrderById(orderEvent.OrderId)
        if order is not None and order.Type == OrderType.OptionExercise:
            self.Liquidate(order.Symbol, "Option exercised")


class VIXDaily(PythonData):
    """Custom VIX data from local CSV. Format: Date,Close"""

    def GetSource(self, config, date, isLive):
        return SubscriptionDataSource(
            "/Lean/Data/custom/vix_daily.csv",
            SubscriptionTransportMedium.LocalFile,
        )

    def Reader(self, config, line, date, isLive):
        if not line.strip() or line.startswith("Date"):
            return None
        parts = line.split(",")
        if len(parts) < 2:
            return None
        entry = VIXDaily()
        try:
            event_date = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
            entry.Symbol = config.Symbol
            entry.Time = event_date + timedelta(hours=12)
            entry.Value = float(parts[1].strip())
        except (ValueError, IndexError):
            return None
        return entry
