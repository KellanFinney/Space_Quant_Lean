"""This implements a mean reversion strategy on the EURO USD pair. We expect the price to 
stay somewhere around its 20 day mean. We do not expect it to deviate from its 
20 day moving average that much. We use standard devation to measure the devation. If it moves 
above it by 2 standard devation we take a short, if it moves below we go long. This is 
accomplished by the bollinger band function that is already built-in"""

from AlgorithmImports import *
from System.Drawing import Color 

class ForexBollingerBandBot(QCAlgorithm):
    def Initialize(self):
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(100000)
        self.pair = self.AddForex("EURUSD", Resolution.Daily, Market.FXCM).Symbol
        self.bb = self.BB(self.pair, 20, 2)

        stockPlot = Chart("Trade Plot")
        stockPlot.AddSeries(Series("Buy", SeriesType.Scatter, "$", Color.Green, 
                                ScatterMarkerSymbol.Triangle))

        stockPlot.AddSeries(Series("Sell", SeriesType.Scatter, "$", Color.Red, 
                                ScatterMarkerSymbol.TriangleDown))
        
        stockPlot.AddSeries(Series("Liquidate", SeriesType.Scatter, "$", Color.Blue, 
                                ScatterMarkerSymbol.Diamond))
        self.AddChart(stockPlot)


    def OnData(self, data): 
        if not self.bb.IsReady:
            return 

        price = data[self.pair].Price
        self.Plot("Trade Plot", "Price", price)
        self.Plot("Trade Plot", "MiddleBand", self.bb.MiddleBand.Current.Value)
        self.Plot("Trade Plot", "UpperBand", self.bb.UpperBand.Current.Value)
        self.Plot("Trade Plot", "LowerBand", self.bb.LowerBand.Current.Value)

        
        if not self.Portfolio.Invested:
            if self.bb.LowerBand.Current.Value > price:
                self.SetHoldings(self.pair, 1)
                self.Plot("Trade Plot", "Buy", price)
            elif self.bb.UpperBand.Current.Value < price:
                self.SetHoldings(self.pair, -1)
                self.Plot("Trade Plot", "Sell", price)
        else:
            if self.Portfolio[self.pair].IsLong:
                if self.bb.MiddleBand.Current.Value < price:
                    self.Liquidate()
                    self.Plot("Trade Plot", "Liquidate", price)
            elif self.bb.MiddleBand.Current.Value > price:
                self.Liquidate()
                self.Plot("Trade Plot", "Liquidate", price)


