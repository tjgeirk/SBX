import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import asyncio
import time

tf = '5m'
max_leverage = 5
take_profit = 0.2
stop_loss = 0.1
martingale = 0.01
trade_risk = 0.25


exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})

async def fetch_data(coin):
    df = pd.DataFrame(await exchange.fetch_ohlcv(coin, '15m'), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    df = df.drop(columns=['volume'])
    df = df.ta.ema(length=14)
    return df


async def train_model(df):
    X = df.drop(columns=['close'])
    y = df['close']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print('Model Accuracy:', accuracy)
    return model


async def predict(model, df):
    X_live = df.tail(1).drop(columns=['close'])
    y_live = model.predict(X_live)
    return y_live


async def process_coin(coin, positions, model):
    df = await fetch_data(coin)
    signal = await predict(model, df)
    order = Order(coin)

    for x in positions:
        if x['symbol'] != coin:
            continue
        else:
            if x['side'] == 'long':
                if x['percentage'] >= abs(martingale):
                    await order.buy(x['markPrice'], x['side'])
                    print(f"Martingale at {x['percentage']*100}%")
                if x['percentage'] <= -abs(stop_loss):
                    await order.sell(x['markPrice'], x['side'], x['contracts'])
                    print(f"Stop-Loss at {x['percentage']*100}%")
                if x['percentage'] >= abs(take_profit):
                    await order.sell(x['markPrice'], x['side'], x['contracts'])
                    print(f"Take-Profit at {x['percentage']*100}%")

            elif x['side'] == 'short':
                if x['percentage'] >= abs(martingale):
                    await order.sell(x['markPrice'], x['side'])
                    print(f"Martingale at {x['percentage']*100}%")
                if x['percentage'] <= -abs(stop_loss):
                    await order.buy(x['markPrice'], x['side'], x['contracts'])
                    print(f"Stop-Loss at {x['percentage']*100}%")
                if x['percentage'] >= abs(take_profit):
                    await order.buy(x['markPrice'], x['side'], x['contracts'])
                    print(f"Take-Profit at {x['percentage']*100}%")

    if signal == 1:
        # Buy
        await order.buy()
    elif signal == -1:
        # Sell
        await order.sell()


class Order:
    def __init__(self, coin):
        self.coin = coin
        self.balance = None
        self.lever = None
        self.last = None
        self.q = None

    async def _params(self):
        balance = float((await exchange.fetch_balance())['USDT']['total'])
        lever = min(max_leverage, (await exchange.load_markets())[self.coin]['info']['maxLeverage'])
        last = float((await exchange.fetch_ticker(self.coin))['last'])
        q = max([float(balance/last)*0.01, 1])
        self.balance = balance
        self.lever = lever
        self.last = last
        self.q = q
        return {'balance': self.balance, 'lever': self.lever, 'last': self.last, 'q': self.q}

    async def _place_stop_limit_order(self, side, size, target):
        try:
            stop_price = target + \
                ((side == 'sell') - (side == 'buy')) * \
                (target * martingale / self.lever)
            await exchange.create_stop_limit_order(self.coin, side, size, stop_price, stop_price, {'closeOrder': True})
        except ccxt.BaseError as e:
            print('Issue Placing Stop!', e)

    async def sell(self, price=None, side=None, qty=None):
        await self._params()
        print('sell', self.coin)
        size = qty or self.q
        target = price or self.last

        try:
            await exchange.create_limit_sell_order(self.coin, size, target, {'leverage': self.lever, 'closeOrder': side == 'long'})
        except ccxt.BaseError as e:
            print('Issue Selling!', e)

    async def buy(self, price=None, side=None, qty=None):
        await self._params()
        print('buy', self.coin)
        size = qty or self.q
        target = price or self.last

        try:
            await exchange.create_limit_buy_order(self.coin, size, target, {'leverage': self.lever, 'closeOrder': side == 'short'})
        except ccxt.BaseError as e:
            print('Issue Buying!', e)


async def process_open_orders(coin):
    now = time.time()
    open_orders = await exchange.fetch_open_orders(coin)
    for order in open_orders:
        if now - order['timestamp'] / 1000 > 300:
            await exchange.cancel_order(order['id'])


async def run_strategy():
    while True:
        positions = await exchange.fetch_positions()
        ordered_coins = sorted(
            markets.values(), key=lambda x: x['info']['priceChgPct'], reverse=True)
        coins = set([x['symbol'] for x in ordered_coins][0:5] + [x['symbol'] for x in positions])
        tasks = [asyncio.create_task(process_coin(
            coin, positions, model)) for coin in coins]
        await asyncio.gather(*tasks)
        await asyncio.sleep(4 * 60 * 60)


async def main():
    df = await fetch_data('BTC/USDT')
    model = await train_model(df)
    await run_strategy()


async def main():
    while True:
        markets = await exchange.load_markets()
        ordered_coins = sorted(
            markets.values(), key=lambda x: x['info']['priceChgPct'], reverse=True)
        positions = await exchange.fetch_positions()
        coins = set([x['symbol'] for x in ordered_coins]
                    [0:5] + [x['symbol'] for x in positions])
        tasks = [asyncio.create_task(process_coin(
            coin, positions)) for coin in coins]
        await asyncio.gather(*tasks)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


while __name__ == '__main__':

    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(e)
