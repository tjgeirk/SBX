
# SBX v1.2.1
import time
import ccxt
from ta import trend, momentum, volatility
from pandas import DataFrame as dataframe, Series as series

tf = '1m'
max_leverage = 1
max_open_trades = 5
picker_override = None
exclude = []

exchange = ccxt.kucoinfutures(
    {
        'apiKey': '',
        'secret': '',
        'password': '',
        'adjustForTimeDifference': True,
    }
)


def picker():
    if picker_override is not None:
        return picker_override
    else:
        markets = exchange.load_markets(True)
        coins = []
        while len(coins) < max_open_trades:
            picker = {}
            for v in markets:
                if v in (exclude or coins):
                    continue
                else:
                    picker[v] = [markets[v]['info']['priceChgPct']]
            pick = max(picker.values())
            for i, v in picker.items():
                if pick == v:
                    coin = i
                    coins.append(coin)
                    break

    if len(coins) == max_open_trades:
        return coins


def getPosition(coin):
    time.sleep(exchange.rateLimit / 1000)
    positions = exchange.fetch_positions()
    df = {}
    for col in ['symbol', 'contracts', 'side', 'percentage', 'liquidationPrice']:
        df[col] = 0
        for v in positions:
            if v['symbol'] == coin:
                df[col] = v[col]
    return series(df)


def getData(coin, tf=tf, source='mark'):
    data = {}
    for x in ['open', 'high', 'low', 'close', 'volume']:
        data[x] = {}
    df = dataframe(exchange.fetch_ohlcv(coin, tf, params={'price': source}))
    data['volume'] = df[5]
    data['close'] = (df[1] + df[2] + df[3] + df[4]) / 4
    for i in range(0, len(df)):
        data['open'][i] = (
            ((df[1][i] + df[4][i]) / 2)
            if i == 0
            else ((df[1][i - 1] + df[4][i - 1]) / 2)
        )
        data['high'][i] = max(df[1][i], df[4][i], df[2][i])
        data['low'][i] = min(df[1][i], df[4][i], df[3][i])
    return dataframe(data)


data = lambda ohlcv='close': getData(coin, tf)[ohlcv]


def getOrderInfo(coin):
    market = exchange.market(coin)
    lever = market['info']['maxLeverage']
    if max_leverage < lever:
        lever = max_leverage
    lotSize = market['contractSize']
    balance = exchange.fetch_balance()['USDT']['free'] * 0.5
    qty = balance / data('close').iloc[-1]
    if qty > lotSize:
        lots = int(qty / lotSize) * lever
    elif qty < lotSize:
        lots = int(lotSize / qty) * lever
    else:
        return {'lots': 1, 'lever': lever}
    return {'lots': lots, 'lever': lever}


class Order:
    def __init__(self):
        self.bid = exchange.fetch_l2_order_book(coin)['bids'][0][0]
        self.ask = exchange.fetch_l2_order_book(coin)['asks'][0][0]
        self.side = getPosition(coin)['side']
        self.lever = getOrderInfo(coin)['lever']
        self.lots = getOrderInfo(coin)['lots']

    def buy(self, price=None):
        try:
            print('BUY')
            if self.side != 'short':
                price = self.ask if price is None else price
                exchange.create_limit_order(
                    coin,
                    'buy',
                    self.lots,
                    price,
                    {'leverage': self.lever, 'timeInForce': 'GTC'},
                )

            elif self.side == 'short':
                price = self.bid if price is None else price
                exchange.create_limit_order(
                    coin,
                    'buy',
                    self.lots,
                    price,
                    {'closeOrder': True, 'reduceOnly': True, 'timeInForce': 'GTC'},
                )
        except Exception as e:
            print(e)

    def sell(self, price=None):
        try:
            print('SELL')
            if self.side != 'long':
                price = self.bid if price is None else price
                exchange.create_limit_order(
                    coin,
                    'sell',
                    self.lots,
                    price,
                    {'leverage': self.lever, 'timeInForce': 'GTC'},
                )

            elif self.side == 'long':
                price = self.ask if price is None else price
                exchange.create_limit_order(
                    coin,
                    'sell',
                    self.lots,
                    price,
                    {'closeOrder': True, 'reduceOnly': True, 'timeInForce': 'GTC'},
                )
        except Exception as e:
            print(e)


ema = lambda window, df='close', period=- \
    1: trend.ema_indicator(data(df), window).iloc[period]

kama = lambda window=3, period=-1: \
    momentum.kama(data('close'), window).iloc[period]


def stoch(window=13, smooth=3, period=-1):
    stoch = momentum.stoch(data('high'), data(
        'low'), data('close'), window, smooth)
    signal = momentum.stoch_signal(data('high'), data(
        'low'), data('close'), window, smooth)
    return {'stoch': stoch.iloc[period], 'signal': signal.iloc[period], 'hist': (stoch-signal).iloc[period]}


def bot(coin):
    order = Order()
    print(coin)

    if (ema(5) < ema(8) < ema(13)
        and data('close').iloc[-1] > ema(5)
        and data('close').iloc[-2] > ema(5, 'close', -2)
        and stoch()['hist'] > 0
            and stoch()['stoch'] < 30):
        order.buy()

    if (ema(5) > ema(8) > ema(13)
        and data('close').iloc[-1] < ema(5)
        and data('close').iloc[-2] < ema(5, 'close', -2)
        and stoch()['hist'] < 0
            and stoch()['stoch'] > 70):
        order.sell()

    if getPosition(coin)['side'] == 'long':
        exchange.create_stop_limit_order(
            coin, 'sell', 1, kama(), kama(), {
                'closeOrder':True, 
                'reduceOnly':True, 
                'stop':'down'})

    if getPosition(coin)['side'] == 'short':
        exchange.create_stop_limit_order(
            coin, 'buy', 1, kama(), kama(), {
                'closeOrder': True,
                'reduceOnly': True,
                'stop': 'up'})

while True:
    try:
        for coin in series(picker()):
            bot(coin)
            time.sleep(exchange.rateLimit / 1000)
    except Exception as e:
        print(e)
        time.sleep(exchange.rateLimit / 1000)
        exchange.cancel_all_orders()
        continue
