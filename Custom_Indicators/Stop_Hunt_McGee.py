# Stop Hunt McGee
from statistics import mean
from pandas import DataFrame

def stop_hunt_mcgee(data:DataFrame, window:int=21) -> DataFrame:
    df = {'highs':[],'lows':[]}
    for x in range(1, window+1):
        df['highs'].append(data['high'].iloc[-x])
        df['lows'].append(data['low'].iloc[-x])
    resist_pct = mean(df['highs'])/max(df['highs'])
    support_pct = mean(df['lows'])/min(df['lows'])
    support = (min(df)*support_pct)
    resist = (max(df)*resist_pct)
    return {'sup':support, 'res':resist}
    
