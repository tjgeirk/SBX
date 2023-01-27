import pandas_ta as ta
from time import sleep
from ccxt import kucoinfutures
from pandas import DataFrame as dataframe

tf = '5m'
max_leverage = 5
take_profit = 0.01
stop_loss = 0.2
martingale = 0.01

exchange = kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
})

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
        self.balance = float(exchange.fetch_balance()['USDT']['total'])
        self.lever = exchange.load_markets()[coin]['info']['maxLeverage']
        self.lever = max_leverage if max_leverage < self.lever else self.lever
        self.last = float(exchange.fetch_ticker(coin)['last'])
        self.q = float(self.balance/self.last)*0.01
        self.q = 1 if self.q < 1 else self.q

    def sell(self, price=None, side=None) -> None:
        print('sell', self.coin)
        target = self.last if price == None else price
        (lambda: exchange.create_limit_sell_order(
            self.coin, self.q, target, {'leverage': self.lever, 'closeOrder': True if side == 'long' else False}))()
        (lambda: exchange.create_stop_limit_order(
            self.coin, 'buy', self.q, (target-(target*0.1/self.lever)), (target-(target*0.1/self.lever)), {'closeOrder': True}))()

    def buy(self, price=None, side=None) -> None:
        print('buy', self.coin)
        target = self.last if price == None else price
        (lambda: exchange.create_limit_buy_order(
            self.coin, self.q, target, {'leverage': self.lever, 'closeOrder': True if side == 'short' else False}))()
        (lambda: exchange.create_stop_limit_order(
            self.coin, 'sell', self.q, (target+(target*0.1/self.lever)), (target+(target*0.1/self.lever)), {'closeOrder': True}))()


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'mfi', 'length': 2},
    {'kind': 'adx', 'length': 3},
    {'kind': 'ema', 'close': 'close', 'length': 8},
    {'kind': 'ema', 'close': 'close', 'length': 13},
    {'kind': 'ema', 'close': 'close', 'length': 21},
    {'kind': 'vwma', 'close': 'close', 'length': 200},
])

while True:
    
    sleep(exchange.rateLimit/1000)

    try:
        markets = exchange.load_markets()
        picker = {x: [markets[x]['info']['priceChgPct']] for x in markets}
        picker = sorted(picker, key=lambda y: picker[y], reverse=True)
        positions = [x['symbol'] for x in exchange.fetch_positions()]
        coins = picker[0:5] + positions
    
        if exchange.fetch_balance()['USDT']['free'] >= exchange.fetch_balance()['USDT']['total']/5:
            for coin in coins:

                sleep(exchange.rateLimit/1000)
                df = Data(coin, tf)
                order = Order(coin)
                df.ta.strategy(SBX)
                orders = exchange.fetch_open_orders(
                    coin, params={'stop': True})
                
                if len(orders) >= 3*len(positions):
                    try:
                        tif = max([x['timestamp'] for x in orders])
                
                        for x in orders:
                            if x['timestamp'] < tif:
                                exchange.cancel_order(x['id'])
                                sleep(exchange.rateLimit/1000)
                
                    except Exception:
                        pass
                
                if df['EMA_8'].iloc[-1] > df['EMA_13'].iloc[-1] > df['EMA_21'].iloc[-1] > df['VWMA_200'].iloc[-1]:

                    if (
                            df['DMP_3'].iloc[-1] >
                            df['DMN_3'].iloc[-1] and
                            df['MFI_2'].iloc[-1] >= 50 and
                            df['HA_close'].iloc[-1] >
                            df['HA_open'].iloc[-1]):
                        order.buy()

                if df['EMA_8'].iloc[-1] < df['EMA_13'].iloc[-1] < df['EMA_21'].iloc[-1] < df['VWMA_200'].iloc[-1]:

                    if (
                            df['DMP_3'].iloc[-1] <
                            df['DMN_3'].iloc[-1] and
                            df['MFI_2'].iloc[-1] <= 50 and
                            df['HA_close'].iloc[-1] <
                            df['HA_open'].iloc[-1]):
                        order.sell()

        for x in exchange.fetch_positions():
            sleep(exchange.rateLimit/1000)
            coin = x['symbol']
            order = Order(coin)

            if x['side'] == 'long':
                if x['percentage'] <= -abs(martingale):
                    try:
                        order.buy(x['markPrice'])
                    except Exception:
                        if x['percentage'] <= -abs(stop_loss):
                            order.sell(x['markPrice'], x['side'])
                elif x['percentage'] >= abs(take_profit):
                    order.sell(x['markPrice'], x['side'])
            elif x['side'] == 'short':
                if x['percentage'] <= -abs(martingale):
                    try:
                        order.sell(x['markPrice'])
                    except Exception:
                        if x['percentage'] <= -abs(stop_loss):
                            order.buy(x['markPrice'], x['side'])
                elif x['percentage'] >= abs(take_profit):
                    order.buy(x['markPrice'], x['side'])

            age = x['info']['currentTimestamp'] - x['info']['openingTimestamp']

            if age > 300_000:
                order.sell(x['markPrice'], x['side']) if x['side'] == 'long' else order.buy(
                    x['markPrice'], x['side'])

    except Exception as e:
        print(e)
        sleep(exchange.rateLimit/1000)
        continue
