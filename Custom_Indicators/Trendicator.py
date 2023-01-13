# Trendicator
from ta import trend
from pandas import DataFrame, Series

def Trendicator(data:DataFrame, window:int=21, signal:int=8) -> DataFrame:
    sma = lambda col: trend.sma_indicator(data[col], window)
    trendicator = {}
    trendicator['upper_band'] = sma(sma('high', window), window)
    trendicator['open_line'] = sma(sma('open', signal), window)
    trendicator['close_line'] = sma(sma('close', signal), window)
    trendicator['lower_band'] = sma(sma('low', window), window)
    return DataFrame(trendicator)
