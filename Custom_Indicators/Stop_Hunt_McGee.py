# Stop Hunt McGee
from statistics import mean
from pandas import DataFrame

def Stop_Hunt_McGee(data:DataFrame, window:int=21) -> DataFrame:
    highs = []
    lows = []
    for x in range(1, window+1):
        highs.append(data('high').iloc[-window-x])
        lows.append(data('low').iloc[-window-x])
    resist_pct = max(highs)/mean(highs)
    support_pct = min(lows)/mean(lows)
    support = (min(lows)*support_pct)
    resist = (max(highs)*resist_pct)
    return {'sup':support, 'res':resist}
