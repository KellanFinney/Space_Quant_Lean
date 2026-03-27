"""
Bitcoin neural network swing strategy.

Loads a pre-trained Keras model (trained by lesson16_neural_net.py) from
Data/custom/bitcoin_model.json and uses it to predict BTC price direction.
Goes 100% long when model predicts "up", 50% short when "down".

Uses local LEAN: model config + weights from Data/custom/bitcoin_model.json.
Crypto data required at Data/crypto/bitfinex/daily/btcusd.zip.
"""

from AlgorithmImports import *
from tensorflow.keras.models import Sequential
import numpy as np
import json


class BitcoinNeuralNet(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)

        model_path = "/Lean/Data/custom/bitcoin_model.json"
        try:
            with open(model_path) as f:
                model_data = json.load(f)
            self.model = Sequential.from_config(model_data["config"])
            weights = [np.array(w) for w in model_data["weights"]]
            self.model.set_weights(weights)
            self.model_loaded = True
            self.Debug(f"Neural net model loaded from {model_path}")
        except Exception as e:
            self.Debug(f"Failed to load model: {e}")
            self.model_loaded = False

        self.SetBrokerageModel(BrokerageName.Bitfinex, AccountType.Margin)
        self.symbol = self.AddCrypto("BTCUSD", Resolution.Daily).Symbol
        self.SetBenchmark(self.symbol)

    def OnData(self, data):
        if not self.model_loaded:
            return

        prediction = self.GetPrediction()
        if prediction == "up":
            self.SetHoldings(self.symbol, 1)
        elif prediction == "down":
            self.SetHoldings(self.symbol, -0.5)

    def GetPrediction(self):
        df = self.History(self.symbol, 31, Resolution.Daily)
        if df.empty or len(df) < 31:
            return "neutral"

        df_change = df[["open", "high", "low", "close", "volume"]].pct_change().dropna()
        if len(df_change) < 30:
            return "neutral"

        model_input = df_change.tail(30).values
        model_input = np.expand_dims(model_input, axis=0)

        if round(self.model.predict(model_input)[0][0]) == 0:
            return "down"
        return "up"
