import time
import datetime
from ccxt import kucoinfutures as kcf
from pandas import DataFrame as dataframe
from ta import volume, volatility, trend

lever = 20
tf = '1m'
coin = 'MATIC/USDT:USDT'
lots = 1


exchange = kcf({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})

exchange.load_markets()


def getData(coin, tf):
    time.sleep(exchange.rateLimit / 1000)
    data = exchange.fetch_ohlcv(coin, tf, limit=500)
    df = {}
    for i, col in enumerate(['date', 'open', 'high', 'low', 'close',
                             'volume']):
        df[col] = []
        for row in data:
            if col == 'date':
                df[col].append(datetime.datetime.fromtimestamp(row[i] / 1000))
            else:
                df[col].append(row[i])
        DF = dataframe(df)
    return DF


def getPositions():
    positions = exchange.fetch_positions()
    df = {}
    df[coin] = {}
    for _, col in enumerate(['contracts', 'side', 'percentage', 'unrealizedPnl']):
        df[coin][col] = 0
        for (_, v) in enumerate(positions):
            if v['symbol'] == coin:
                df[coin][col] = v[col]
        DF = dataframe(df)
    return DF


class order:
    def buy():
        if getPositions()[coin]['side'] != 'short' and price.close() > sma(200):
            exchange.create_limit_order(
                coin, 'buy', lots,
                price.ask(), {'leverage': lever})
        elif getPositions()[coin]['side'] == 'short':
            exchange.create_limit_order(coin, 'buy', getPositions()[coin]['contracts'], price.bid(), {
                'closeOrder': True, 'reduceOnly': True})
        else:
            print('Order not placed due to 200MA rule.')

    def sell():
        if getPositions()[coin]['side'] != 'long' and price.close() < sma(200):
            exchange.create_limit_order(
                coin, 'sell', lots, price.bid(), {'leverage': lever})
        elif getPositions()[coin]['side'] == 'long':
            exchange.create_limit_order(coin, 'sell', getPositions()[coin]['contracts'], price.ask(), {
                'closeOrder': True, 'reduceOnly': True})
        else:
            print('Order not placed due to 200MA rule.')


class price:
    def open(period=-1):
        return (getData(coin, tf)['close'].iloc[period-1] +
                getData(coin, tf)['open'].iloc[period-1])/2

    def close(period=-1):
        return (getData(coin, tf)['close'].iloc[period] +
                getData(coin, tf)['high'].iloc[period] +
                getData(coin, tf)['low'].iloc[period] +
                getData(coin, tf)['open'].iloc[period])/4

    def high(period=-1):
        return getData(coin, tf)['high'].iloc[period]

    def low(period=-1):
        return getData(coin, tf)['low'].iloc[period]

    def ask(index=0):
        return exchange.fetch_order_book(coin)['asks'][index][0]

    def bid(index=0):
        return exchange.fetch_order_book(coin)['bids'][index][0]


class bands:
    def upper(window=20, devs=1, period=-1):
        return volatility.bollinger_hband(getData(coin, tf)['close'], window, devs).iloc[period]

    def mid(window=20, devs=1, period=-1):
        return volatility.bollinger_mavg(getData(coin, tf)['close'], window, devs).iloc[period]

    def lower(window=20, devs=1, period=-1):
        return volatility.bollinger_lband(getData(coin, tf)['close'], window, devs).iloc[period]


def mfi(window=8, period=-1):
    return volume.money_flow_index(getData(coin, tf)['high'], getData(coin, tf)['low'], getData(coin, tf)['close'], getData(coin, tf)['volume'], window).iloc[period]


def sma(window=5, ohlcv='close', period=-1):
    return trend.sma_indicator(getData(coin, tf)[ohlcv], window).iloc[period]


print(getPositions())
while True:
    try:
        overbought = oversold = False
        for x in range(1, 6):
            if price.low(-x) <= bands.lower(20, 2, -x):
                print(f'Oversold {x} bars ago.')
                oversold = True
            if price.high(-x) >= bands.upper(20, 2, -x):
                print(f'Overbought {x} bars ago.')
                overbought = True
        if (oversold and not overbought and mfi(2) - mfi(3) >= 0) or (
                getPositions()[coin]['side'] == 'long'):
            print(f'Buy signal. Confirming reversal...')
            count = 0
            while not (mfi(2) and mfi(3)) <= 70:
                try:
                    time.sleep(exchange.rateLimit / 1000)
                    count += 1
                    print(f'Reversal confirmed. Buy cycles: {count}')
                    order.buy()
                except Exception as e:
                    print(e)
                    continue
            else:
                print('No confirmation. Ending Cycle.')
                order.sell() if getPositions()[
                    coin]['side'] == 'long' else exchange.cancel_all_orders()
        if (overbought and not oversold and mfi(2) - mfi(3) <= 0) or (
                getPositions()[coin]['side'] == 'short'):
            print(f'Sell signal. Confirming reversal...')
            count = 0
            while not (mfi(2) and mfi(3)) >= 30:
                try:
                    time.sleep(exchange.rateLimit / 1000)
                    count += 1
                    print(f'Reversal confirmed. Sell cycles: {count}')
                    order.sell()
                except Exception as e:
                    print(e)
                    continue
            else:
                print('No confirmation. Ending Cycle.')
                order.buy() if getPositions()[
                    coin]['side'] == 'short' else exchange.cancel_all_orders()
    except Exception as e:
        print(e)
        continue
