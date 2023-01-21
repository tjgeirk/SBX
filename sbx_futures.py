import pandas_ta as ta
from time import sleep
from ccxt import kucoinfutures
from pandas import DataFrame as dataframe

tf = '5m'
max_leverage = 5

exchange = kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
})

exchange.cancel_all_orders(params={'stop': True})


def Data(coin: str, tf: str = tf) -> dataframe:
    data = {}
    for i, v in enumerate(['date', 'open', 'high', 'low', 'close', 'volume']):
        data[v] = {}
        for n, x in enumerate(exchange.fetch_ohlcv(coin, tf, limit=1000)):
            data[v][n] = x[i]
    return dataframe(data)


SBX = ta.Strategy(name='SBX', ta=[
    {'kind': 'ha'},
    {'kind': 'stoch'},
    {'kind': 'ema', 'close': 'close', 'length': 20},
    {'kind': 'ema', 'close': 'close', 'length': 50},
    {'kind': 'ema', 'close': 'close', 'length': 200}])


def longIsOkay(coin, tf):
    df = Data(coin, tf)
    df.ta.strategy(SBX)
    return True if df['EMA_20'].iloc[-1] > df['EMA_50'].iloc[-1] > df['EMA_200'].iloc[-1] else False


def shortIsOkay(coin, tf):
    df = Data(coin, tf)
    df.ta.strategy(SBX)
    return True if df['EMA_20'].iloc[-1] < df['EMA_50'].iloc[-1] < df['EMA_200'].iloc[-1] else False


while True:
    markets = exchange.load_markets()
    picker = {x: [markets[x]['info']['priceChgPct']] for x in markets}
    picker = sorted(picker, key=lambda y: picker[y], reverse=True)
    coins = [x['symbol'] for x in exchange.fetch_positions()] + picker[0:5]

    for coin in coins:
        print(coin)
        while longIsOkay(coin, tf) is True:
            try:
                df = Data(coin, tf)
                df.ta.strategy(SBX)

                ticker = exchange.fetch_ticker(coin)
                balance = exchange.fetch_balance()['USDT']['free']
                price = ticker['last']

                lever = exchange.markets[coin]['info']['maxLeverage']
                lever = max_leverage if max_leverage < lever else lever

                qty = (balance*lever/price)/10
                qty = 1 if qty < 1 else qty

                orders = exchange.fetch_open_orders(coin)

                if len(orders) >= 3:
                    tif = max([x['timestamp'] for x in orders])
                    for x in orders:
                        if x['timestamp'] < tif:
                            exchange.cancel_order(x['id'])

                if df['STOCHk_14_3_3'].iloc[-1] < df['STOCHd_14_3_3'].iloc[-1]:
                    exchange.create_limit_buy_order(
                        coin, qty, price, {'leverage': lever})

                for x in exchange.fetch_positions():

                    if x['percentage'] >= 0.1 and x['side'] == 'long':
                        exchange.create_limit_sell_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

                    elif x['percentage'] >= 0.1 and x['side'] == 'short':
                        exchange.create_limit_buy_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

                    elif x['percentage'] <= -0.1 and x['side'] == 'long':
                        exchange.create_limit_sell_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

                    elif x['percentage'] <= -0.1 and x['side'] == 'short':
                        exchange.create_limit_buy_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})
            except Exception as e:
                print(e)
                continue

        for x in exchange.fetch_positions():
            try:

                if x['side'] == 'long' and longIsOkay(coin, tf) is False:
                    exchange.create_limit_sell_order(
                        x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

            except Exception as e:
                print(e)
                continue

        while shortIsOkay(coin, tf) is True:
            try:
                df = Data(coin, tf)
                df.ta.strategy(SBX)

                ticker = exchange.fetch_ticker(coin)
                balance = exchange.fetch_balance()['USDT']['free']
                price = ticker['last']

                lever = exchange.markets[coin]['info']['maxLeverage']
                lever = max_leverage if max_leverage < lever else lever

                qty = (balance*lever/price)/100
                qty = 1 if qty < 1 else qty

                orders = exchange.fetch_open_orders(coin)

                if len(orders) >= 3:
                    tif = max([x['timestamp'] for x in orders])
                    for x in orders:
                        if x['timestamp'] < tif:
                            exchange.cancel_order(x['id'])

                if df['STOCHk_14_3_3'].iloc[-1] > df['STOCHd_14_3_3'].iloc[-1]:
                    exchange.create_limit_sell_order(
                        coin, qty, price, {'leverage': lever})

                for x in exchange.fetch_positions():

                    if x['percentage'] >= 0.1 and x['side'] == 'short':
                        exchange.create_limit_buy_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

                    elif x['percentage'] >= 0.1 and x['side'] == 'long':
                        exchange.create_limit_sell_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

                    elif x['percentage'] <= -0.1 and x['side'] == 'short':
                        exchange.create_limit_buy_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

                    elif x['percentage'] <= -0.1 and x['side'] == 'long':
                        exchange.create_limit_sell_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

            except Exception as e:
                print(e)
                continue

            for x in exchange.fetch_positions():
                try:

                    if x['side'] == 'short' and shortIsOkay(coin, tf) is False:
                        exchange.create_limit_buy_order(
                            x['symbol'], x['contracts'], x['markPrice'], {'closeOrder': True})

                except Exception as e:
                    print(e)
                    continue
