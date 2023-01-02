# Stop Hunt McGee
from statistics import mode
from pandas import DataFrame

def Stop_Hunt_McGee(data:DataFrame, window:int=21) -> DataFrame:
    highs = lows = []
    for x in range(1, window+1):
        highs.append(data('high').iloc[-x])
        lows.append(data('low').iloc[-x])
    support = mode(lows)
    resist =  mode(highs)
    return {'sup':support, 'res':resist}

