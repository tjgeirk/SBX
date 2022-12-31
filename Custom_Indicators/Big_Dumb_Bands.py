# Big Dumb Bands
from ta import volatility
from pandas import DataFrame

def Big_Dumb_Bands(data:DataFrame, fast_window:int=3, slow_window:int=5):
    dc = lambda window: volatility.donchian_channel_pband(data['high'], data['low'], data['close'], window)
    if dc(fast_window).iloc[-1] == dc(slow_window).iloc[-1] == 1:
        return 'UP'
    elif dc(fast_window).iloc[-1] == dc(slow_window).iloc[-1] == 0:
        return 'DOWN'
    else:
        return None
