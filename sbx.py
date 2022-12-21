# SBX v1.2.1
import time
import datetime
from ccxt import kucoinfutures as kcf
from ta import trend, momentum
from pandas import DataFrame as dataframe, Series as series

# List of one or more timeframes to check for signals.
# timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
timeframes = ['1m']

# Maximum leverage to use. If this number is higher than is available... 
# (if set to 100 but the max is 20, for example...), 
# ...the maximum leverage is used instead
# (...the order will be placed with the leverage set to 20 rather than 100). 
max_leverage = 5

# Option to specify which coin to trade. 
# If set to None and no positions are open, the highest gainer is automatically selected.
# If set to None and there is an open position, the bot will continue to trade the open position.
# picker_override = 'BTC/USDT:USDT'
picker_override = None

# Option to exclude coins. If no exclusions, leave list empty.
# excludes = ['SOS/USDT:USDT', 'DOGE/USDT:USDT']
excludes = []

# Input API credentials here to begin. Be safe! Have fun!
exchange = kcf({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})


### End of configuration! ###


exchange.load_markets()

def picker():
    if picker_override is not None:
        return picker_override
    markets = exchange.load_markets(True)
    picker = {}
    coin = str()
    for v in markets:
        if v in excludes:
            continue
        else:
            picker[v] = [markets[v]['info']['priceChgPct']]
    pick = max(picker.values())
    for i, v in picker.items():
        if pick == v:
            coin = i
            break
    return coin


coin = picker()

for pos in exchange.fetch_positions():
    if picker() == pos['symbol']:
        continue
    else:
        coin = pos['symbol']
        break
print(coin)


def getPositions():
    time.sleep(exchange.rateLimit / 1000)
    positions = exchange.fetch_positions()
    df = {}
    df[coin] = {}
    for col in ['contracts', 'side', 'percentage', 'liquidationPrice']:
        df[coin][col] = 0
        for v in positions:
            if v['symbol'] == coin:
                df[coin][col] = v[col]
        DF = dataframe(df)
    return DF


def getData(coin, tf, source='mark'):
    time.sleep(exchange.rateLimit / 1000)
    data = exchange.fetch_ohlcv(coin, tf, params={'price': source})
    df = {}
    for i, col in enumerate(['date', 'open', 'high', 'low', 'close',
                             'volume']):
        df[col] = []
        for row in data:
            if col == 'date':
                df[col].append(datetime.datetime.fromtimestamp(row[i] / 1000))
            else:
                df[col].append(row[i])
    df = dataframe(df).drop('date', axis=1)
    df['open_ha'] = df['low_ha'] = df['high_ha'] = series(dtype=float)
    for i in range(0, len(df)):
        if i == 0:
            df['open_ha'][i] = (df['open'][i] + df['close'][i]) / 2
        else:
            df['open_ha'][i] = (df['open'][i - 1] + df['close'][i - 1]) / 2
        df['high_ha'][i] = max(df['open'][i], df['close'][i], df['high'][i])
        df['low_ha'][i] = min(df['open'][i], df['close'][i], df['low'][i])
    df['close_ha'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    return dataframe(df)


def ema(window=21, df=getData(coin, tf)['close_ha']):
    return trend.ema_indicator(df, window)


def stoch(window=14, smooth=3):
    stoc = momentum.stoch(
        getData(coin, tf)['high'],
        getData(coin, tf)['low'],
        getData(coin, tf)['close'],
        window, smooth)
    signal = momentum.stoch_signal(
        getData(coin, tf)['high'],
        getData(coin, tf)['low'],
        getData(coin, tf)['close'],
        window, smooth)
    return {'stoch': stoc, 'signal': signal, 'hist': stoc - signal}


class Order:
    def __init__(self):
        self.bid = exchange.fetch_l2_order_book(coin)['bids'][0][0]
        self.ask = exchange.fetch_l2_order_book(coin)['asks'][0][0]
        self.mark = (self.ask + self.bid) / 2
        self.market = exchange.market(coin)
        self.side = getPositions()[coin]['side']
        self.lever = self.market['info']['maxLeverage']
        if max_leverage < self.lever:
            self.lever = max_leverage
        self.lotSize = self.market['contractSize']
        self.balance = exchange.fetch_balance()['USDT'][
            'free'] * 0.99
        self.qty = self.balance / self.mark
        if self.qty > self.lotSize:
            self.lots = int(self.qty / self.lotSize) * self.lever
        elif self.qty < self.lotSize:
            self.lots = int(self.lotSize / self.qty) * self.lever

    def buy(self, price):
        print('BUY')
        if self.side != 'short':
            exchange.create_limit_order(
                coin,
                'buy',
                self.lots,
                price,
                {'leverage': self.lever,
                 'timeInForce': 'GTC'})
        elif self.side == 'short':
            exchange.create_limit_order(
                coin,
                'buy',
                self.lots,
                price,
                {'closeOrder': True,
                 'reduceOnly': True,
                 'timeInForce': 'GTC'})

    def sell(self, price):
        print('SELL')
        if self.side != 'long':
            exchange.create_limit_order(
                coin,
                'sell',
                self.lots,
                price,
                {'leverage': self.lever,
                 'timeInForce': 'GTC'})

        elif self.side == 'long':
            exchange.create_limit_order(
                coin,
                'sell',
                self.lots,
                price,
                {'closeOrder': True,
                 'reduceOnly': True,
                 'timeInForce': 'GTC'})


while True:
    try:
        if getPositions()[coin]['side'] is None:
            coin = picker()

        order = Order()


        if (
                stoch(5, 3)['hist'].iloc[-1] < 0 and
                ema(5).iloc[-1] >
                ema(8).iloc[-1] >
                ema(13).iloc[-1] and
                getData(coin, tf)['close_ha'].iloc[-1] <
                getData(coin, tf)['open_ha'].iloc[-1] and
                getData(coin, tf)['close_ha'].iloc[-2] <
                getData(coin, tf)['open_ha'].iloc[-2]):
                while getPositions()[coin]['side'] != 'short':
                    try:
                        order.sell(order.ask)
                    except Exception:
                        time.sleep(exchange.rateLimit/1000)
                        exchange.cancel_all_orders()
                        continue


        if (
                stoch(5, 3)['hist'].iloc[-1] > 0 and
                ema(5).iloc[-1] <
                ema(8).iloc[-1] <
                ema(13).iloc[-1] and
                getData(coin, tf)['close_ha'].iloc[-1] >
                getData(coin, tf)['open_ha'].iloc[-1] and
                getData(coin, tf)['close_ha'].iloc[-2] >
                getData(coin, tf)['open_ha'].iloc[-2]):
                while getPositions()[coin]['side'] != 'long':
                    try:
                        order.buy(order.bid)
                    except Exception:
                        time.sleep(exchange.rateLimit/1000)
                        exchange.cancel_all_orders()
                        continue


        if (
                getPositions()[coin]['side'] == 'long' and
                stoch(5, 3)['hist'].iloc[-1] < 0):
            order.sell(order.bid)


        if (
                getPositions()[coin]['side'] == 'short' and
                stoch(5, 3)['hist'].iloc[-1] > 0):
            order.buy(order.ask)


    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit/1000)
        continue
