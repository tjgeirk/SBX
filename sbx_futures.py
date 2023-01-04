# SBX v1.2.1
import time
import ccxt
from ta import trend, momentum
from pandas import DataFrame as dataframe

tf = '15m'
max_leverage = 20
picker_override = None
exclude = []

exchange = ccxt.kucoinfutures({
        'apiKey': '',
        'secret': '',
        'password': '',
        'adjustForTimeDifference': True,
    }
)

def picker() -> str:
    markets = exchange.load_markets(True)
    picker = {}
    for v in markets:
        if v in exclude:
            continue
        else:
            picker[v] = [markets[v]['info']['priceChgPct']]
    pick = max(picker.values())
    for i, v in picker.items():
        if pick == v:
            coin = i
            return coin

coin = picker()

def getPosition(coin:str=coin) -> dict:
    time.sleep(exchange.rateLimit / 1000)
    positions = exchange.fetch_positions()
    for x in positions:
        if x['symbol'] == coin:
            return x

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


def takeProfits() -> None:
    try:
        for x in exchange.fetch_positions():
            if x['percentage'] >= 0.02:
                exchange.create_limit_sell_order(x['symbol'], x['contracts'], x['markPrice'], {'closeOrder':True, 'timeInForce':'GTC'})
    except Exception as e:
        print(e)

print(coin)
while True:
    balance = exchange.fetch_balance()['USDT']['free']
    if coin != picker():
        print(picker())
        coin = picker()
    open = data(coin)['open'].iloc[-1]
    close = data(coin)['close'].iloc[-1]
    maximum = exchange.load_markets()[coin]['info']['maxLeverage']
    lever = max_leverage if max_leverage < maximum else maximum
    qty = (balance/close) * 0.5 * lever
    kama = momentum.kama(data()['close']).iloc[-1]

    try:
        side = getPosition(coin)['side']
    except:
        side = None

    try:
        if close > kama and qty >= 1 and side != 'long':
            print('BUY')
            exchange.create_market_order(coin, 'buy', qty, None, {'leverage': lever})

        elif close < kama and qty >= 1 and side != 'short':
            print('SELL')
            exchange.create_market_order(coin, 'sell', qty, None, {'leverage': lever})
        else:
            print('...')
        takeProfits()

    except Exception as e:
        print(e)
