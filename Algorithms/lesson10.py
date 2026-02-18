"""This strategy uses the 30 day simple moving average and trades SPY and BND. 
if SMA < SPY then we are 80% SPY and 20% BND, if SMA > SPY we are 80% BND and 20% SPY
""" 

from AlgorithmImports import *

class AlertRedHyena(QCAlgorithm): 
    def Initialize(self):
        self.set_start_date(2020, 12, 24)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100000)
        self.spy  = self.AddEquity("SPY", Resolution.Daily).Symbol 
        self.bnd = self.AddEquity("BND", Resolution.Daily).Symbol

        self.sma = self.SMA(self.spy, 30, Resolution.Daily)
        self.rebalanceTime = datetime.min 
        self.uptrend = True 

    def OnData(self, data):
        if not self.sma.IsReady or self.spy not in data or self.bnd not in data:
            return 

        if data[self.spy].Price >= self.sma.Current.Value:
            if self.Time >= self.rebalanceTime or not self.uptrend:
                self.SetHoldings(self.spy, 0.8)
                self.SetHoldings(self.bnd, 0.2)
                self.uptrend = True 
                self.rebalanceTime = self.Time + timedelta(30)
        elif self.Time >= self.rebalanceTime or self.uptrend:
            self.SetHoldings(self.spy, 0.2)
            self.SetHoldings(self.bnd, 0.8)
            self.uptrend = False 
            self.rebalanceTime = self.Time + timedelta(30)
        self.Plot("Benchmark", "SMA", self.sma.Current.Value)

    
