"""This strategy implements buys call option if the price breaks out of its 1 month 
high price. IF a new high price is reached we will buy an At the Money call option. Close 
all options shortly before expiration"""

from AlgorithmImports import *

class BreakoutCallOptionBot(QCAlgorithm):

    def Initializer(self):
        self.set_start_date(2018, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(100000)
        equity = self.AddEquity("MSFT", Resolution.Minute) 
        equity.setDataNormalizationMode(DataNormalizationMode.Raw)
        self.equity = equity.Symbol 
        self.SetBenchmark(self.equity)

        option = self.AddOption("MSFT", Resolution.Minute)
        #we are buying at the money calls here 
        option.SetFilter(-3, 3, timedelta(20), timedelta(40))
        #this keeps track of the high price of the euqity from the past month 
        self.high = self.MAX(self.equity, 21, Resolution.Daily, Field.High)

    def OnData(self, data):
        if not self.high.IsReady:
            return 

        #check if we have open positions - create list and make sure it is of the type option 
        option_invested = [x.Key for X in self.Portfolio if x.Value.Invested and 
                           x.Value.Type==SecurityType.Option]
        #check if there is enough time before expiration - we liquidate 4 days before expiration
        if option_invested: 
            if self.Time +timedelta(4) > option_invested[0].ID.Date:
                self.Liquidate(option_invested[0], "Too close to expiration")
            return 
        #Now we check if the underlying made a new high
        if self.Securities[self.equity].Price >= self.high.Current.Value:
            for i in data.OptionChains:
                chains = i.Value 
                self.BuyCall(chains)
    
    #filter the option chain 
    def BuyCall(self, chains):
        expiry = sorted(chains,key = lambda x: x.Expiry, reverse=True)[0].Expiry
        calls = [i for i in chains if i.Expiry == expiry and i.Right == OptionsRight.Call]
        call_contracts = sorted(calls.key = lambda x: abs(x.Strike - x.UnderlyingLastPrice))
        if len(call_contracts) == 0:
            return
        self.call = call_contracts[0]

        quantity = self.Portfolio.TotalPortfolioValue / self.call.AskPrice
        quantity = int( 0.05 * quantity / 100)
        self.Buy(self.call.Symbol, quantity)

    def OnOrderEvent(self, orderEvent):
        order = self.Transactions.GetOrderById(oderEvent.OrderId)
        if order.Type == orderType.OptionExercise:
            self.Liquate()
    
    
        