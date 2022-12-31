# Trendicator
from ta import trend
from pandas import DataFrame, Series

def Trendicator(data:DataFrame, window:int=8, signal:int=21) -> DataFrame:
    sma = lambda col: trend.sma_indicator(data[col], window)
    trendicator = {}
    trendicator['upper_band'] = sma(sma('high', window), window)
    trendicator['signal_line'] = sma(sma('close', signal), window)
    trendicator['lower_band'] = sma(sma('low', window), window)
    return DataFrame(trendicator)
