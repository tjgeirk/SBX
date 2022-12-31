# Smoothed Money Flow Divergence
from ta import volume, trend, momentum
from pandas import DataFrame

def smfd(dataframe:DataFrame, window:int=5, smooth:int=3, signal:int=3) -> DataFrame:
    SMFD = {}
    money_flow = volume.money_flow_index(dataframe['high'], dataframe['low'], dataframe['close'], dataframe['volume'], window)
    smoothed_money_flow =  trend.sma_indicator(money_flow, smooth)
    kama_signal = momentum.kama(smoothed_money_flow, signal)
    histogram = smoothed_money_flow - kama_signal
    return DataFrame({'hist':histogram, 'smf':smoothed_money_flow, 'signal':kama_signal})
