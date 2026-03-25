from AlgorithmImports import *


class FundamentalFactorAlphaModel(AlphaModel):
    def __init__(self):
        self.rebalanceTime = datetime.min
        self.sectors = {}
        # e.g. {technology: set(AAPL, TSLA, ..), healthcare: set(ABC, XYZ, ..)}

    def Update(self, algorithm, data):
        if algorithm.Time <= self.rebalanceTime:
            return []
        self.rebalanceTime = Expiry.EndOfQuarter(algorithm.Time)

        insights = []

        for sector in self.sectors:
            securities = list(self.sectors[sector])
            if not securities:
                continue

            sortedByROE = sorted(
                securities,
                key=lambda x: x.Fundamentals.OperationRatios.ROE.Value,
                reverse=True,
            )
            sortedByPM = sorted(
                securities,
                key=lambda x: x.Fundamentals.OperationRatios.NetMargin.Value,
                reverse=True,
            )
            sortedByPE = sorted(
                securities,
                key=lambda x: x.Fundamentals.ValuationRatios.PERatio,
                reverse=False,
            )

            scores = {}
            for security in securities:
                score = sum(
                    [
                        sortedByROE.index(security),
                        sortedByPM.index(security),
                        sortedByPE.index(security),
                    ]
                )
                scores[security] = score

            length = max(int(len(scores) / 5), 1)
            for security, _score in sorted(scores.items(), key=lambda x: x[1], reverse=False)[:length]:
                symbol = security.Symbol
                insights.append(Insight.Price(symbol, Expiry.EndOfQuarter, InsightDirection.Up))

        return insights

    def OnSecuritiesChanged(self, algorithm, changes):
        for security in changes.RemovedSecurities:
            for sector in self.sectors:
                if security in self.sectors[sector]:
                    self.sectors[sector].remove(security)

        for security in changes.AddedSecurities:
            sector = security.Fundamentals.AssetClassification.MorningstarSectorCode
            if sector not in self.sectors:
                self.sectors[sector] = set()
            self.sectors[sector].add(security)