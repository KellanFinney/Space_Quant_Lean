from AlgorithmImports import *
import csv
from io import StringIO

class RKLBSwingStrategy(QCAlgorithm):
    """
    Rocket Lab (RKLB) Swing Trading Strategy
    
    Signals:
    1. Technical: RSI, MACD, SMA crossover (20/50)
    2. Event-driven: Rocket Lab launch calendar (buy before launches, momentum after)
    3. Position sizing: $1,000 account, long-only, 1-5 trades/week
    
    Rules:
    - Long only (no shorting - $1k account can't margin)
    - Max 1 position at a time (concentrated due to small account)
    - Stop loss at 5% to protect capital
    - Take profit at 8-12% 
    - Hold 1-5 days (swing trade)
    """
    
    def Initialize(self):
        # Backtest period: RKLB IPO to present
        self.set_start_date(2021, 9, 1)  # Month after RKLB IPO
        self.set_end_date(2025, 3, 31)
        self.set_cash(1000)
        
        # Warmup for indicators
        self.SetWarmUp(timedelta(days=60))
        
        # Add RKLB equity
        self.rklb = self.add_equity("RKLB", Resolution.Daily).Symbol
        
        # Load launch schedule as custom data
        self.launch_data = self.add_data(RocketLabLaunch, "RKLBLAUNCHES", Resolution.Daily).Symbol
        
        # ---- Technical Indicators ----
        # RSI (14-period) - Overbought/Oversold
        self.rsi = self.RSI(self.rklb, 14, MovingAverageType.Wilders, Resolution.Daily)
        
        # MACD (12, 26, 9) - Trend & Momentum
        self.macd = self.MACD(self.rklb, 12, 26, 9, MovingAverageType.Exponential, Resolution.Daily)
        
        # Simple Moving Averages - Trend direction
        self.sma_fast = self.SMA(self.rklb, 20, Resolution.Daily)  # 20-day (1 month)
        self.sma_slow = self.SMA(self.rklb, 50, Resolution.Daily)  # 50-day (quarter)
        
        # Bollinger Bands - Volatility & Mean Reversion
        self.bb = self.BB(self.rklb, 20, 2, MovingAverageType.Simple, Resolution.Daily)
        
        # ---- Trade Management ----
        self.entry_price = 0
        self.entry_date = None
        self.stop_loss_pct = 0.05       # 5% stop loss
        self.take_profit_pct = 0.10     # 10% take profit
        self.max_hold_days = 10         # Max 10 trading days hold
        self.trades_this_week = 0
        self.last_week = -1
        self.max_trades_per_week = 5
        
        # Launch event tracking
        self.upcoming_launch = False
        self.days_to_launch = 999
        self.last_launch_outcome = None
        self.days_since_launch = 999
        
        # Signal scoring
        self.signal_log = []
        
    def OnData(self, data):
        if self.IsWarmingUp:
            return
            
        # Reset weekly trade counter
        current_week = self.Time.isocalendar()[1]
        if current_week != self.last_week:
            self.trades_this_week = 0
            self.last_week = current_week
        
        # Process launch events
        if self.launch_data in data:
            launch = data[self.launch_data]
            if launch.Value == 1:  # Upcoming launch (within 5 days)
                self.upcoming_launch = True
                self.days_to_launch = int(launch["DaysToLaunch"])
            elif launch.Value == 2:  # Launch just happened
                self.days_since_launch = 0
                self.last_launch_outcome = launch["Outcome"]
                self.upcoming_launch = False
                self.Log(f"LAUNCH EVENT: {launch['Mission']} - {self.last_launch_outcome}")
        
        # Increment days since launch
        self.days_since_launch += 1
        
        # Check if we have RKLB price data
        if self.rklb not in data or data[self.rklb] is None:
            return
            
        price = self.Securities[self.rklb].Price
        if price <= 0:
            return
        
        # ---- MANAGE EXISTING POSITION ----
        if self.Portfolio[self.rklb].Invested:
            self.ManagePosition(price)
            return
        
        # ---- GENERATE ENTRY SIGNALS ----
        if self.trades_this_week >= self.max_trades_per_week:
            return
            
        if not (self.rsi.IsReady and self.macd.IsReady and self.sma_fast.IsReady and self.sma_slow.IsReady):
            return
        
        signal_score = self.CalculateSignalScore(price)
        
        # Enter long if combined signal is strong enough
        if signal_score >= 3:
            # Calculate position size (use up to 95% of portfolio)
            available_cash = self.Portfolio.Cash * 0.95
            shares = int(available_cash / price)
            
            if shares > 0:
                self.MarketOrder(self.rklb, shares)
                self.entry_price = price
                self.entry_date = self.Time
                self.trades_this_week += 1
                self.Log(f"BUY {shares} RKLB @ ${price:.2f} | Signal: {signal_score} | RSI: {self.rsi.Current.Value:.1f} | MACD: {self.macd.Current.Value:.4f}")
    
    def CalculateSignalScore(self, price):
        """
        Calculate a composite signal score (0-7).
        Each indicator contributes 0 or 1 point. Need >= 3 to enter.
        """
        score = 0
        reasons = []
        
        # 1. RSI Oversold Recovery (RSI was < 35, now rising)
        rsi_val = self.rsi.Current.Value
        if 30 < rsi_val < 45:
            score += 1
            reasons.append(f"RSI oversold recovery ({rsi_val:.1f})")
        
        # 2. MACD Bullish Crossover (signal line cross)
        macd_val = self.macd.Current.Value
        macd_signal = self.macd.Signal.Current.Value
        macd_hist = self.macd.Histogram.Current.Value
        if macd_val > macd_signal and macd_hist > 0:
            score += 1
            reasons.append(f"MACD bullish ({macd_hist:.4f})")
        
        # 3. SMA Golden Cross (fast > slow = uptrend)
        sma_fast_val = self.sma_fast.Current.Value
        sma_slow_val = self.sma_slow.Current.Value
        if sma_fast_val > sma_slow_val:
            score += 1
            reasons.append(f"SMA uptrend (20d: {sma_fast_val:.2f} > 50d: {sma_slow_val:.2f})")
        
        # 4. Price above 20-day SMA (momentum)
        if price > sma_fast_val:
            score += 1
            reasons.append(f"Price above SMA20")
        
        # 5. Bollinger Band bounce (price near lower band)
        bb_lower = self.bb.LowerBand.Current.Value
        bb_middle = self.bb.MiddleBand.Current.Value
        if price < bb_lower * 1.02:  # Within 2% of lower band
            score += 1
            reasons.append(f"Near Bollinger lower band")
        
        # 6. Upcoming launch (buy the hype, 1-5 days before)
        if self.upcoming_launch and 1 <= self.days_to_launch <= 5:
            score += 1
            reasons.append(f"Launch in {self.days_to_launch} days")
        
        # 7. Post-successful launch momentum (within 3 days)
        if self.days_since_launch <= 3 and self.last_launch_outcome == "Success":
            score += 1
            reasons.append(f"Post-launch momentum ({self.days_since_launch}d ago)")
        
        if score >= 3:
            self.Log(f"SIGNAL SCORE: {score}/7 | {' | '.join(reasons)}")
        
        return score
    
    def ManagePosition(self, price):
        """Manage open position with stop loss, take profit, and time stop"""
        if self.entry_price <= 0:
            return
            
        pnl_pct = (price - self.entry_price) / self.entry_price
        days_held = (self.Time - self.entry_date).days if self.entry_date else 0
        
        # Stop Loss
        if pnl_pct <= -self.stop_loss_pct:
            self.Liquidate(self.rklb)
            self.Log(f"STOP LOSS: Sold RKLB @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
            self.ResetPosition()
            return
        
        # Take Profit
        if pnl_pct >= self.take_profit_pct:
            self.Liquidate(self.rklb)
            self.Log(f"TAKE PROFIT: Sold RKLB @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
            self.ResetPosition()
            return
        
        # Time Stop - exit if held too long
        if days_held >= self.max_hold_days:
            self.Liquidate(self.rklb)
            self.Log(f"TIME STOP: Sold RKLB @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
            self.ResetPosition()
            return
        
        # Trailing stop: if up > 5%, tighten stop to 2%
        if pnl_pct > 0.05:
            trailing_stop = self.entry_price * 1.03  # Lock in at least 3%
            if price <= trailing_stop:
                self.Liquidate(self.rklb)
                self.Log(f"TRAILING STOP: Sold RKLB @ ${price:.2f} | P&L: {pnl_pct*100:.1f}% | Held {days_held} days")
                self.ResetPosition()
                return
    
    def ResetPosition(self):
        """Reset position tracking variables"""
        self.entry_price = 0
        self.entry_date = None
    
    def OnEndOfAlgorithm(self):
        """Liquidate all at end of backtest"""
        if self.Portfolio.Invested:
            self.Liquidate()
            self.Log("END OF BACKTEST - Liquidating all positions")


class RocketLabLaunch(PythonData):
    """
    Custom data source: Rocket Lab launch schedule
    Generates signals:
    - Value=1: Upcoming launch (within 5 days)
    - Value=2: Launch day
    """
    
    _launches = None  # Class-level cache
    
    def GetSource(self, config, date, isLive):
        return SubscriptionDataSource(
            "/Lean/Data/custom/rklb_launches.csv",
            SubscriptionTransportMedium.LocalFile
        )
    
    def Reader(self, config, line, date, isLive):
        if not line.strip() or line.startswith("Date"):
            return None
            
        data = line.split(',')
        if len(data) < 4:
            return None
            
        launch = RocketLabLaunch()
        
        try:
            launch_date = datetime.strptime(data[0].strip(), "%Y-%m-%d")
            launch.Symbol = config.Symbol
            
            # On launch day
            launch.Time = launch_date + timedelta(hours=12)
            launch.Value = 2  # Launch event
            launch["Mission"] = data[1].strip()
            launch["FlightNo"] = data[2].strip()
            launch["Outcome"] = data[3].strip()
            launch["DaysToLaunch"] = "0"
            
        except (ValueError, IndexError):
            return None
        
        return launch
