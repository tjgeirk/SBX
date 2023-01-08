import statistics
import time
import ccxt
from matplotlib import pyplot as plt
from ta import momentum, volatility, trend
from pandas import DataFrame as dataframe
import pandas_ta as pta
tf = '5m'
max_leverage = 5
picker_override = None
exclude = []

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
})


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


def Data(coin: str, tf: str = tf, source: str = 'mark') -> dataframe:
    d = {}
    for x in ['date', 'open', 'high', 'low', 'close', 'volume']:
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


def Bands(window=20, atrs=2) -> dataframe:
    df = {}
    atr = volatility.average_true_range(
        data['high'], data['low'], data['close'], window)
    df['middle'] = momentum.kama(data['close'], window)
    df['upper'] = df['middle']+(atrs*atr)
    df['lower'] = df['middle']-(atrs*atr)
    return dataframe(df)


def AverageDirectionalIndex(window=28): return pta.adx(
    data['high'], data['low'], data['close'], window)


def b(): return float(exchange.fetch_balance()['USDT']['free'])
def ma(window: int = 200): return trend.ema_indicator(data['close'], window)
def ml(): return exchange.load_markets()[coin]['info']['maxLeverage']
def lever(): return max_leverage if max_leverage < ml() else ml()
def hi(): return Bands()['upper']
def md(): return Bands()['middle']
def lo(): return Bands()['lower']
def o(): return data['open']
def h(): return data['high']
def l(): return data['low']
def c(): return data['close']
def t(): return exchange.fetch_ticker(coin)
def q(): return (b()/c().iloc[-1])*lever()*0.1
def bid(): return t()['info']['bestBidPrice']
def ask(): return t()['info']['bestAskPrice']
def adx(): return AverageDirectionalIndex()['ADX_28'].iloc[-1]


coin = None
while True:
    try:
        if coin != picker():
            unsettled = exchange.fetch_open_orders(coin)
            for x in unsettled:
                if x['info']['closeOrder'] != True:
                    exchange.cancel_order(x['id'])
            coin = picker()
            print(coin)
        data = Data(coin, tf)

        if lever() > 5:
            print(
                'oh F*CK! BIG DUMB IDIOT MODE IS CURRENTLY ACTIVATED!!! REDUCE LEVERAGE OR YOU WILL DIED!!!')
        time.sleep(exchange.rateLimit/500)
        if adx() > 20 and q() >= 1:
            if c().iloc[-1] > ma(50).iloc[-1] > ma(200).iloc[-1]:
                print(f'BUYING {coin}.')
                exchange.create_market_order(
                    coin, 'buy', q(), {'leverage': lever})
            elif c().iloc[-1] < ma(50).iloc[-1] < ma(200).iloc[-1]:
                print(f'SELLING {coin}.')
                exchange.create_market_sell_order(
                    coin, q(), {'leverage': lever})
        time.sleep(exchange.rateLimit/500)
        if adx() < 20 and q() >= 1:
            if (c().iloc[-1] < lo().iloc[-1]):
                print(f'BUYING {coin}.')
                exchange.create_limit_buy_order(
                    coin, q(), ask(), {'leverage': lever()})
            elif (c().iloc[-1] > hi().iloc[-1]):
                print(f'SELLING {coin}.')
                exchange.create_limit_sell_order(
                    coin, q(), bid(), {'leverage': lever()})
        time.sleep(exchange.rateLimit/500)
        for x in exchange.fetch_positions():
            print(f'Checking {x["symbol"]} position status...')
            time.sleep(exchange.rateLimit/500)
            if x['percentage'] >= 0.02:
                print('Placing stop...')
                try:
                    exchange.create_stop_limit_order(coin, 'sell' if x['side'] == 'long' else 'buy', x['contracts'], x['entryPrice'], x['entryPrice'], {
                                                     'closeOrder': True, 'stop': 'down' if x['side'] == 'long' else 'up'})
                except Exception:
                    continue
            time.sleep(exchange.rateLimit/500)
            if x['side'] == 'long':
                if x['markPrice'] > hi().iloc[-1] or x['percentage'] <= -0.05:
                    print(f'CLOSING {x["symbol"]}.')
                    exchange.create_limit_sell_order(
                        x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})
            elif x['side'] == 'short':
                if x['markPrice'] < lo().iloc[-1] or x['percentage'] <= -0.05:
                    print(f'CLOSING {x["symbol"]}.')
                    exchange.create_limit_buy_order(
                        x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})
            time.sleep(exchange.rateLimit/500)
            if adx() > 20 and q() >= 1:
                print('ADX Detects a Trend...')
                if c().iloc[-1] > ma(50).iloc[-1] > ma(200).iloc[-1]:
                    print(f'BUYING {x["symbol"]}.')
                    exchange.create_limit_order(
                        x['symbol'], 'buy', q(), x['markPrice'], {'leverage': lever})
                elif c().iloc[-1] < ma(50).iloc[-1] < ma(200).iloc[-1]:
                    print(f'SELLING {x["symbol"]}.')
                    exchange.create_limit_sell_order(
                        x['symbol'], q(), x['markPrice'], {'leverage': lever})
            elif adx() < 20 and q() >= 1:
                print('ADX Detects a Range...')
                if (c().iloc[-1] < lo().iloc[-1]):
                    print(f'BUYING {x["symbol"]}.')
                    exchange.create_limit_buy_order(
                        x['symbol'], q(), ask(), {'leverage': lever()})
                elif (c().iloc[-1] > hi().iloc[-1]):
                    print(f'BUYING {x["symbol"]}.')
                    exchange.create_limit_sell_order(
                        x['symbol'], q(), bid(), {'leverage': lever()})
            time.sleep(exchange.rateLimit/500)
    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit/500)
        continue
