# SBX v1.2.1
import time
import ccxt
from ta import trend, momentum, volatility
from pandas import DataFrame as dataframe, Series as series
tf = '1m'

exchange = ccxt.kucoin(
    {
        'apiKey': '',
        'secret': '',
        'password': ''
    }
)


def picker():
    pairlist = []
    markets = exchange.load_markets(True)
    for x in markets:
        time.sleep(exchange.rateLimit/1000)
        if "/USDT" in x:
            pairlist.append(x)
    pick = {}
    ticks = exchange.fetch_tickers()
    for n in pairlist:
        time.sleep(exchange.rateLimit/1000)
        pick[n] = ticks[n]['percentage']
    m = max(pick.values())
    coin = None
    for i,v in pick.items():
        coin = i if v == m else coin
    return coin        

coin=picker()
print(coin)


# %%
def targetPrice(coin=coin):
    df = {}
    for a in ['asks', 'bids']:
        df[a] = {}
        for x,y in exchange.fetch_order_book(coin, 20)[a]:
            time.sleep(exchange.rateLimit/1000)
            df[a][x] = y
            if max(df[a].values()) == y:
                df[a]['target'] = x
                df[a]['weight'] = y
            else:
                continue
    return {
        'buyPrice': df['bids']['target'], 
        'buyWeight': df['bids']['weight'], 
        'sellPrice': df['asks']['target'], 
        'sellWeight': df['bids']['weight']
    }

print(targetPrice())


# %%
def getData(coin=coin, tf=tf, source='mark'):
    time.sleep(exchange.rateLimit/1000)
    data = {}
    for x in ['open', 'high', 'low', 'close', 'volume']:
        time.sleep(exchange.rateLimit/1000)
        data[x] = {}
    df = dataframe(exchange.fetch_ohlcv(coin, tf, params={'price': source}))
    data['volume'] = df[5]
    data['close'] = (df[1] + df[2] + df[3] + df[4]) / 4
    for i in range(0, len(df)):
        time.sleep(exchange.rateLimit/1000)
        data['open'][i] = (
            ((df[1][i] + df[4][i]) / 2)
            if i == 0
            else ((df[1][i - 1] + df[4][i - 1]) / 2)
        )
        data['high'][i] = max(df[1][i], df[4][i], df[2][i])
        data['low'][i] = min(df[1][i], df[4][i], df[3][i])
    return dataframe(data)


data = lambda ohlcv='close': getData(coin, tf)[ohlcv]


# %%

ema = lambda window=8, df='close', period= -1: \
    trend.ema_indicator(data(df), window).iloc[period]

bands = lambda window=20, devs=1, period=-1: volatility.bollinger_pband(
    data('close'), window, devs).iloc[period]

def stoch(window=14, smooth=3, period=-1):
    stoch = momentum.stoch(data('high'), data(
        'low'), data('close'), window, smooth)
    signal = momentum.stoch_signal(data('high'), data(
        'low'), data('close'), window, smooth)
    return {'stoch': stoch.iloc[period], 'signal': signal.iloc[period], 'hist': (stoch-signal).iloc[period]}


# %%
while True:
    try:
        time.sleep(exchange.rateLimit/1000)
        balance = lambda coin=coin: exchange.fetch_balance()[coin]['free']
        wallet = coin.replace('/USDT', '')
        if coin != picker:
            if balance(wallet) == 0:
                coin = picker()
            else:
                continue

        if (data('close').iloc[-1] > ema(8) > ema(13) > ema(21) and stoch()['hist'] > 0 and bands() > 1):
               exchange.create_limit_buy_order(
                coin, targetPrice(coin)['buyPrice']/(balance('USDT')/2),
                targetPrice(coin)['buyPrice'])

        if (stoch()['hist'] < 0 and bands() < 1 
            and data('close').iloc[-1] < ema(8)):
                exchange.create_limit_sell_order(
                coin, (balance/targetPrice(coin)['buyPrice']),
                targetPrice(coin)['buyPrice'])
    except Exception as e:
        time.sleep(exchange.rateLimit/1000)
        print(e)


