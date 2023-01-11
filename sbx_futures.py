import statistics
import time
import ccxt
import pandas_ta as ta
from matplotlib import pyplot as plt
from pandas import DataFrame as dataframe

tf = '5m'
max_leverage = 5
picker_override = None
exclude = []
include = []

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
})

no_signal = []
def picker() -> str:
    z = None
    picker = {}
    markets = exchange.load_markets(True)
    while z is None:
        for v in markets:
            if v in (no_signal or exclude):
                continue
            else:
                picker[v] = markets[v]['info']['priceChgPct']
        pick = max(picker.values())
        for i, v in picker.items():
            if pick == v:
                z = i
    return z


def Data(coin: str, tf: str = tf) -> dataframe:
    data = {}
    for i, v in enumerate(['date', 'open', 'high', 'low', 'close', 'volume']):
        data[v] = {}
        for n, x in enumerate(exchange.fetch_ohlcv(coin, tf, limit=1000)):
            data[v][n] = x[i]
    return dataframe(data)


class Order:
    def __init__(self, coin: str) -> None:
        self.coin = coin
        self.b = float(exchange.fetch_balance()['USDT']['free'])
        self.ml = exchange.load_markets()[coin]['info']['maxLeverage']
        self.lever = max_leverage if max_leverage < self.ml else self.ml
        self.t = exchange.fetch_ticker(coin)
        self.bid = float(self.t['info']['bestBidPrice'])
        self.ask = float(self.t['info']['bestAskPrice'])
        self.last = float(self.t['last'])
        self.q = ((self.b)/self.last)

    def buy(self) -> None:
        print('BUY')
        exchange.create_limit_buy_order(self.coin, self.q, self.ask, {
                                        'leverage': self.lever})

    def sell(self) -> None:
        print('SELL')
        exchange.create_limit_sell_order(self.coin, self.q, self.bid, {
                                         'leverage': self.lever})

    def takeProfits(self) -> None:
        for x in exchange.fetch_positions():
            if x['percentage'] >= 0.02:
                try:
                    exchange.create_stop_limit_order(self.coin, 'sell' if x['side'] == 'long' else 'buy', x['contracts'], x['entryPrice'], x['entryPrice'], {
                                                     'closeOrder': True, 'stop': 'down' if x['side'] == 'long' else 'up'})
                except Exception:
                    continue

            if ((x['side'] == 'long' and close < ma(21)) or (x['side'] == 'short' and close > ma(20))):
                try:
                    exchange.create_limit_order(self.coin, 'sell' if x['side'] == 'long' else 'buy', x['contracts'], x['markPrice'], {
                                                'closeOrder': True, 'stop': 'down' if x['side'] == 'long' else 'up'})
                except Exception:
                    continue


while True:
    try:
        coins = include
        for x in exchange.fetch_positions():
            coins.append(x['symbol'])
        if picker() not in coins:
            coins.append(picker())

        for x in exchange.fetch_open_orders():
            if x['symbol'] not in coins:
                exchange.cancel_order(x['id'])

        for coin in set(coins):
            data = Data(coin, tf)
            order = Order(coin)
            print(coin)

            def ma(window): return ta.ma(
                'ema', data['close'], length=window).iloc[-1]
            open = data.ta.ha()['HA_open'].iloc[-1]
            close = data.ta.ha()['HA_close'].iloc[-1]

            if order.q >= 1:

                if ta.decreasing(data.ta.adx(length=200)['ADX_200']).iloc[-1] == 1:
                    print(f'Dropping {coin} from trade pairs list.')
                    no_signal.append(coin)
                    if len(no_signal) >= 20:
                        for x in no_signal:
                            if ta.increasing(Data(x, tf).ta.adx(length=50)['ADX_50']).iloc[-1] == 1:
                                no_signal.remove(x)

                elif ta.increasing(
                        data.ta.adx(length=200)['ADX_200']).iloc[-1] == 1:
                    if ma(20) > ma(50) > ma(200) and open < close:
                        order.buy()
                    elif ma(20) < ma(50) < ma(200) and open > close:
                        order.sell()
            order.takeProfits()

            open_orders = sorted(
                exchange.fetch_open_orders(coin), key=lambda x: x['timestamp'], reverse=True)
            sorted(open_orders, key=lambda x: x['info']['closeOrder'] == False)
            for i, x in enumerate(open_orders):
                if i == 0:
                    continue
                else:
                    print('Cancelling order', x['id'])
                    exchange.cancel_order(x['id'])

    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit/500)
        continue
