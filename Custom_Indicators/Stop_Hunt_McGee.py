# Stop Hunt McGee
from statistics import mean
from pandas import DataFrame

def KLE(data:DataFrame, window:int=7) -> DataFrame:
    df = {'highs':[],'lows':[]}
    for x in range(1, window+1):
        df['highs'].append(data['high'].iloc[-x])
        df['lows'].append(data['low'].iloc[-x])
    resist_pct = mean(df['highs'])/max(df['highs'])
    support_pct = mean(df['lows'])/min(df['lows'])
    support = (min(df)*support_pct)
    resist = (max(df)*resist_pct)
    return {'sup':support, 'res':resist}
    
book = lambda coin: exchange.fetch_order_book(coin)

for i,v in enumerate(book()['asks'][0]):
    if max(book()['asks'][1]) == book()['asks'][1][i]:
        ask = book()['asks'][0][i]
    if max(book()['bids'][1]) == book()['bids'][1][i]:
        bid = book()['bids'][0][i]
    return {'ask':ask,'bid':bid}
        
    
    
