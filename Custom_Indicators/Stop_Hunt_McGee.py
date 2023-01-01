# Stop Hunt McGee
from statistics import mean
from pandas import DataFrame

def stop_hunt_mcgee(data:DataFrame, window:int=21) -> DataFrame:
    highs = lows = []
    for x in range(1, window+1):
        highs.append(data('high').iloc[-window-x])
        lows.append(data('low').iloc[-window-x])
    resist_pct = mean(highs)/max(highs)
    support_pct = mean(lows)/min(lows)
    support = (min(lows)*support_pct)
    resist = (max(highs)*resist_pct)
    return {'sup':support, 'res':resist}
