from AlgorithmImports import *
from nltk.sentiment import SentimentIntensityAnalyzer

class MyAlgorithm(QCAlgorithm):
    def Initialize(self):
        # Full date range - TSLA IPO to end of 2024
        self.set_start_date(2010, 7, 1)  # Just after TSLA IPO
        self.set_end_date(2024, 12, 31)
        self.set_cash(100000)
        
        # Add warmup period to pre-load TSLA data
        self.SetWarmUp(timedelta(days=30))

        self.tsla = self.add_equity("TSLA", Resolution.Daily).Symbol
        self.musk = self.add_data(MuskTweet, "MUSKTWTS", Resolution.Daily).Symbol
        
        # Accumulate daily sentiment
        self.daily_sentiment = []
        self.last_trade_date = None
        
    def OnData(self, data):
        if self.IsWarmingUp:
            return
        
        # Collect tweet sentiment scores
        if self.musk in data:
            score = data[self.musk].Value
            content = data[self.musk].Tweet
            self.daily_sentiment.append(score)
            self.Debug(f"Tweet: {score:.4f} - {content[:30]}...")
        
        # Trade when we receive TSLA data (once per day)
        if self.tsla in data and data[self.tsla] is not None:
            tsla_bar = data[self.tsla]
            current_date = self.Time.date()
            
            self.Debug(f"TSLA bar received: O={tsla_bar.Open}, H={tsla_bar.High}, L={tsla_bar.Low}, C={tsla_bar.Close}")
            
            # Only trade once per day when we have sentiment data
            if current_date != self.last_trade_date and len(self.daily_sentiment) > 0:
                avg_sentiment = sum(self.daily_sentiment) / len(self.daily_sentiment)
                self.Log(f"Trading on {current_date}: Avg sentiment {avg_sentiment:.4f} from {len(self.daily_sentiment)} tweets, TSLA price: {tsla_bar.Close}")
                
                self.daily_sentiment = []  # Clear for next day
                self.last_trade_date = current_date
                
                if avg_sentiment > 0.1:
                    self.SetHoldings(self.tsla, 1)
                    self.Log(f"BUYING TSLA @ {tsla_bar.Close}")
                elif avg_sentiment < -0.1:
                    self.SetHoldings(self.tsla, -1)
                    self.Log(f"SHORTING TSLA @ {tsla_bar.Close}")
                else:
                    # Neutral sentiment - close positions
                    if self.Portfolio[self.tsla].Invested:
                        self.Liquidate(self.tsla)
                        self.Log(f"LIQUIDATING - Neutral sentiment")

    def OnEndOfAlgorithm(self):
        """Liquidate all positions at end of backtest for accurate P&L"""
        if self.Portfolio.Invested:
            self.Liquidate()
            self.Log("END OF BACKTEST - Liquidating all positions")


class MuskTweet(PythonData):
    sia = SentimentIntensityAnalyzer()

    def GetSource(self, config, date, isLive):
        csv_path = "/Lean/Data/2010_2025muskTweetsPreProcessed.csv"
        return SubscriptionDataSource(csv_path, SubscriptionTransportMedium.LocalFile)

    def Reader(self, config, line, date, isLive):
        if not (line.strip() and line[0].isdigit()):
            return None 
        data = line.split(',')
        tweet = MuskTweet()

        try:
            tweet.Symbol = config.Symbol 
            timestamp_str = data[0].split('+')[0].split('-00:00')[0].strip()
            tweet.Time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=1)
            content = data[1].lower()
            tweet.Value = self.sia.polarity_scores(content)["compound"] 
            tweet["Tweet"] = str(content) 
        except ValueError:
            return None 
        
        return tweet
