# Efficiency Weighted Relative Strength Index
from ta import momentum, trend
from pandas import DataFrame

def EWRSI(data:DataFrame, window:int=5, smooth:int=3) -> DataFrame:
    adaptive_rsi = momentum.rsi(momentum.kama(data, window), window)
    ewrsi = trend.ema_indicator(adaptive_rsi, smooth)
    histogram = adaptive_rsi - ewrsi
    return DataFrame({'ewrsi': ewrsi, 'hist': histogram})
