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
        self.q = (self.b/self.last)*self.lever*0.1

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
                    exchange.create_stop_limit_order(self.coin, 'sell' if x['side'] == 'long' else 'buy', x['contracts'], x['entryPrice'], x['entryPrice'], {'closeOrder': True, 'stop': 'down' if x['side'] == 'long' else 'up'})
                except Exception:
                    continue
            if ((x['side'] == 'long' and  close < open) or (x['side'] == 'short' and open < close)) and x['percentage'] > 0:
                try:
                    exchange.create_limit_order(self.coin, 'sell' if x['side'] == 'long' else 'buy', x['contracts'], x['markPrice'], {'closeOrder': True, 'stop': 'down' if x['side'] == 'long' else 'up'})
                except Exception:
                    continue

last_climate = None
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

        def ma(window): return ta.ma(
            'ema', data['close'], length=window).iloc[-1]
        k = data.ta.stoch()['STOCHk_14_3_3'].iloc[-1]
        d = data.ta.stoch()['STOCHd_14_3_3'].iloc[-1]
        mfi = data.ta.mfi(length=5).iloc[-1]
        open = data.ta.ha()['HA_open'].iloc[-1]
        close = data.ta.ha()['HA_close'].iloc[-1]
        trend = True if ta.increasing(
            data.ta.adx()['ADX_14']).iloc[-1] == 1 else False
        range = True if ta.decreasing(
            data.ta.adx()['ADX_14']).iloc[-1] == 1 else False

        climate = 'Trend' if trend == True else 'Range' if range == True else 'Unsure'

        if climate != last_climate:
            print(climate)
            last_climate = climate

        if Order(coin).q >= 1:

            if trend is True and mfi > 50 and close > ma(20) > ma(50):
                Order(coin).buy()

            if trend is True and mfi < 50 and close < ma(20) < ma(50):
                Order(coin).sell()

            if range is True and 20 > k > d:
                Order(coin).buy()

            if range is True and 80 < k < d:
                Order(coin).sell()

        Order(coin).takeProfits()

    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit/500)
        continue
