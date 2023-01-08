from ccxt import kucoinfutures as exchange
from pandas import DataFrame as dataframe

def data(coin:str=coin, tf:str=tf, source:str='mark') -> dataframe:
    d = {}
    for x in ['open', 'high', 'low', 'close', 'volume']:
        d[x] = {}
    df = dataframe(exchange.fetch_ohlcv(coin, tf, params={'price': source}))
    d['volume'] = df[5]
    d['close'] = (df[1] + df[2] + df[3] + df[4]) / 4
    for i in range(0, len(df)):
        d['open'][i] = (
            ((df[1][i] + df[4][i]) / 2)
            if i == 0
            else ((df[1][i - 1] + df[4][i - 1]) / 2)
        )
        d['high'][i] = max(df[1][i], df[4][i], df[2][i])
        d['low'][i] = min(df[1][i], df[4][i], df[3][i])
    return dataframe(d)
