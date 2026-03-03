from AlgorithmImports import *
import csv 
from io import StringIO


class PLSwingStrategy(QCAlgorithm):
    """
    Planet Labs (PL) Swing Trading Strategy
    
    Signals:
    1. Technical: RSI, MACD, SMA crossover (20/50)
    2. Event-driven: Planet Labs launch calendar (buy before launches, momentum after)
    3. Position sizing: $1,000 account, long-only, 1-5 trades/week
    """

    