"""
Buy and hold quality stocks strategy. 

1.) They have to have IPO's 5+ years ago 
2.) Industries include financial services, real estate, healthcare, utilities, and technology
3.) Rank by PEratio, Margin, ROE: Invest in top 20% of each sector 

"""

from AlgorithmImports import *
from datetime import timedelta
from AlphaModel import *

class BuyAndHoldQualityStocks(QCAlgorithm):

    def Initialize(self):
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(100000)

        self.month = 0 
        self.num_coarse = 500 
        
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseFilterFunction, self.FineSelectionFunction)

        self.AddAlpha(FundamentalFactorAlphaModel())

        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel(self.IsRebalanceDue))

        self.SetRiskManagement(NullRiskManagementModel())

        self.SetExecution(ImmediateExecutionModel())

    def IsRebalanceDue(self, time):
        if time.month == self.month or time.month not in [1, 4, 7, 10]:
            return none 
        self.month = time.month 
        return time 

    

    def CoarseSelectionFunction(self, coarse):
        if not self.IsRebalanceDue(self.Time):
            return Universe.Unchanged 

        selected = sort([x for x in coarse if x.HasfundamentalData and x.Price > 5], 
        key=lambda x: x.DollarVolume, reverse = True) 

        return [x.Symbol for x in selected[:self.num_coarse]]



    def FineSelectionFunction(self, fine):
        sectors = [
            MorningstarSectorCode.FinancialServices, 
            MorningstarSectorCode.RealEstate,
            MorningstarSectorCode.Healthcare,
            MorningstarSectorCode.Utilities,
            MorningstarSectorCode.Technology,
        ] 
        filter_fine = [x.Symbol for x in fine if x.SecurityReference.IPODate + timedelta(5*365) < self.Time 
        and x.AssetClassification.MorningstarSectorCode in sectors 
        and x.OperationRatios.ROE.Value > 0 
        and x.OperationRatios.NetMargin.Value > 0 
        and x.ValuationRatios.PERatio > 0]

        return filtered_fine

