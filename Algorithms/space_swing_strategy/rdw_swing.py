from AlgorithmImports import *


class RDWSwingStrategy(QCAlgorithm):
    """
    Redwire (RDW) Swing Trading Strategy

    Signals:
    1. Technical: RSI, MACD, SMA crossover (20/50), Bollinger Bands
    2. Event-driven: NASA/DARPA contracts, ISS milestones, manufacturing wins
    3. Position sizing: $1,000 account, long-only, 1-5 trades/week

    RDW catalysts:
    - NASA contracts (FabLab, Tipping Point, ISS biotechnology IDIQ)
    - DARPA SabreSat/Otter VLEO demonstration contracts
    - ISS milestones (IROSA solar arrays, 3D bioprint heart tissue)
    - Acquisition of Techshot for in-space manufacturing
    - Earnings on backlog growth ($271M+)

    Rules:
    - Long only (no shorting)
    - Max 1 position at a time
    - Stop loss 7% (space infrastructure, moderate volatility)
    - Take profit 12%
    - Hold 1-10 days (swing trade)
    """

    def Initialize(self):
        self.set_start_date(2021, 11, 1)
        self.set_end_date(2025, 6, 30)
        self.set_cash(1000)

        self.SetWarmUp(timedelta(days=60))

        self.rdw = self.add_equity("RDW", Resolution.Daily).Symbol
        self.event_data = self.add_data(RDWEvent, "RDWEVENTS", Resolution.Daily).Symbol

        # ---- Technical Indicators ----
        self.rsi = self.RSI(self.rdw, 14, MovingAverageType.Wilders, Resolution.Daily)
        self.macd = self.MACD(self.rdw, 12, 26, 9, MovingAverageType.Exponential, Resolution.Daily)
        self.sma_fast = self.SMA(self.rdw, 20, Resolution.Daily)
        self.sma_slow = self.SMA(self.rdw, 50, Resolution.Daily)
        self.bb = self.BB(self.rdw, 20, 2, MovingAverageType.Simple, Resolution.Daily)

        # ---- Trade Management ----
        self.entry_price = 0
        self.entry_date = None
        self.stop_loss_pct = 0.07
        self.take_profit_pct = 0.12
        self.max_hold_days = 10
        self.trades_this_week = 0
        self.last_week = -1
        self.max_trades_per_week = 5

        # ---- Event Tracking ----
        self.last_event_outcome = None
        self.days_since_event = 999
        self.last_event_type = None

    def OnData(self, data):
        if self.IsWarmingUp:
            return

        current_week = self.Time.isocalendar()[1]
        if current_week != self.last_week:
            self.trades_this_week = 0
            self.last_week = current_week

        if self.event_data in data:
            event = data[self.event_data]
            self.days_since_event = 0
            self.last_event_outcome = event["Outcome"]
            self.last_event_type = event["Type"]
            self.Log(f"RDW EVENT: {event['Event']} ({event['Type']}) - {self.last_event_outcome}")

        if self.days_since_event < 999:
            self.days_since_event += 1

        if self.rdw not in data or data[self.rdw] is None:
            return

        price = self.Securities[self.rdw].Price
        if price <= 0:
            return

        if self.Portfolio[self.rdw].Invested:
            self.ManagePosition(price)
            return

        if self.trades_this_week >= self.max_trades_per_week:
            return

        if not (self.rsi.IsReady and self.macd.IsReady and self.sma_fast.IsReady and self.sma_slow.IsReady):
            return

        signal_score = self.CalculateSignalScore(price)

        if signal_score >= 3:
            available_cash = self.Portfolio.Cash * 0.95
            shares = int(available_cash / price)

            if shares > 0:
                self.MarketOrder(self.rdw, shares)
                self.entry_price = price
                self.entry_date = self.Time
                self.trades_this_week += 1
                self.Log(f"BUY {shares} RDW @ ${price:.2f} | Signal: {signal_score} | RSI: {self.rsi.Current.Value:.1f} | MACD: {self.macd.Current.Value:.4f}")

    def CalculateSignalScore(self, price):
        """
        Composite signal score (0-8). Need >= 3 to enter.
        """
        score = 0
        reasons = []

        # 1. RSI oversold recovery
        rsi_val = self.rsi.Current.Value
        if 30 < rsi_val < 45:
            score += 1
            reasons.append(f"RSI oversold recovery ({rsi_val:.1f})")

        # 2. MACD bullish crossover
        macd_val = self.macd.Current.Value
        macd_signal = self.macd.Signal.Current.Value
        macd_hist = self.macd.Histogram.Current.Value
        if macd_val > macd_signal and macd_hist > 0:
            score += 1
            reasons.append(f"MACD bullish ({macd_hist:.4f})")

        # 3. SMA uptrend (fast > slow)
        sma_fast_val = self.sma_fast.Current.Value
        sma_slow_val = self.sma_slow.Current.Value
        if sma_fast_val > sma_slow_val:
            score += 1
            reasons.append(f"SMA uptrend (20d: {sma_fast_val:.2f} > 50d: {sma_slow_val:.2f})")

        # 4. Price above 20-day SMA
        if price > sma_fast_val:
            score += 1
            reasons.append("Price above SMA20")

        # 5. Bollinger Band bounce
        bb_lower = self.bb.LowerBand.Current.Value
        if price < bb_lower * 1.02:
            score += 1
            reasons.append("Near Bollinger lower band")

        # 6. NASA/DARPA contract catalyst
        if self.days_since_event <= 4 and self.last_event_type == "Contract" and self.last_event_outcome == "Success":
            score += 1
            reasons.append(f"Contract catalyst ({self.days_since_event}d ago)")

        # 7. ISS or tech milestone (3D print, IROSA, bioprint)
        if self.days_since_event <= 4 and self.last_event_type == "Milestone" and self.last_event_outcome == "Success":
            score += 1
            reasons.append(f"Tech milestone ({self.days_since_event}d ago)")

        # 8. Earnings catalyst
        if self.days_since_event <= 2 and self.last_event_type == "Earnings" and self.last_event_outcome == "Success":
            score += 1
            reasons.append(f"Earnings catalyst ({self.days_since_event}d ago)")

        if score >= 3:
            self.Log(f"SIGNAL SCORE: {score}/8 | {' | '.join(reasons)}")

        return score

    def ManagePosition(self, price):
        if self.entry_price <= 0:
            return

        pnl_pct = (price - self.entry_price) / self.entry_price
        days_held = (self.Time - self.entry_date).days if self.entry_date else 0

        if pnl_pct <= -self.stop_loss_pct:
            self.Liquidate(self.rdw)
            self.Log(f"STOP LOSS: Sold RDW @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
            self.ResetPosition()
            return

        if pnl_pct >= self.take_profit_pct:
            self.Liquidate(self.rdw)
            self.Log(f"TAKE PROFIT: Sold RDW @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
            self.ResetPosition()
            return

        if days_held >= self.max_hold_days:
            self.Liquidate(self.rdw)
            self.Log(f"TIME STOP: Sold RDW @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
            self.ResetPosition()
            return

        if pnl_pct > 0.05:
            trailing_stop = self.entry_price * 1.03
            if price <= trailing_stop:
                self.Liquidate(self.rdw)
                self.Log(f"TRAILING STOP: Sold RDW @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
                self.ResetPosition()
                return

    def ResetPosition(self):
        self.entry_price = 0
        self.entry_date = None

    def OnEndOfAlgorithm(self):
        if self.Portfolio.Invested:
            self.Liquidate()
            self.Log("END OF BACKTEST - Liquidating all positions")


class RDWEvent(PythonData):
    """
    Custom data source: Redwire NASA/DARPA contracts, ISS milestones, earnings.
    """

    def GetSource(self, config, date, isLive):
        return SubscriptionDataSource(
            "/Lean/Data/custom/rdw_milestones.csv",
            SubscriptionTransportMedium.LocalFile
        )

    def Reader(self, config, line, date, isLive):
        if not line.strip() or line.startswith("Date"):
            return None

        parts = line.split(',')
        if len(parts) < 4:
            return None

        entry = RDWEvent()

        try:
            event_date = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
            entry.Symbol = config.Symbol
            entry.Time = event_date + timedelta(hours=12)
            entry.Value = 1
            entry["Event"] = parts[1].strip()
            entry["Type"] = parts[2].strip()
            entry["Outcome"] = parts[3].strip()
        except (ValueError, IndexError):
            return None

        return entry
