import ccxt.async_support as ccxt
import asyncio
import pandas as pd
import pandas_ta as ta

indicators = ta.Strategy('Indicators', ta=[
    {'kind': 'ha'},
    {'kind': 'ema', 'length': 8, 'close': 'close', 'prefix': 'C'},
    {'kind': 'ema', 'length': 8, 'close': 'open', 'prefix': 'O'},
])


async def strategy(exchange, ticker, balance):
    print(ticker)
    df = pd.DataFrame(await exchange.fetch_ohlcv(ticker, '15m'), columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df.ta.strategy(indicators)
    open_ema = df['O_EMA_8'].iloc[-1]
    close_ema = df['C_EMA_8'].iloc[-1]
    ha_open = df['HA_low'].iloc[-1]
    ha_close = df['HA_high'].iloc[-1]
    close = df['close'].iloc[-1]

    if (open_ema > close_ema) and (ha_open < ha_close):
        await buy_coin(exchange, ticker, close, balance)
    elif (open_ema < close_ema) and (ha_open > ha_close):
        await sell_coin(exchange, ticker, close, balance)


async def buy_coin(exchange, ticker, close, balance):
    balance = balance['free']['USDT']
    amount = balance / 5 / close
    order_params = {'timeInForce': 'GTT', 'cancelAfter': 300}
    await exchange.create_limit_buy_order(ticker, amount, close, order_params)


async def sell_coin(exchange, ticker, close, balance):
    balance = balance['free'][ticker.replace('/USDT', '')]
    order_params = {'timeInForce': 'GTT', 'cancelAfter': 300}
    await exchange.create_limit_sell_order(ticker, balance, close, order_params)


async def main():
    exchange = ccxt.kucoin({
        'apiKey': '',
        'secret': '',
        'password': '',
    })

    while True:
        try:
            balance = await exchange.fetch_balance()
            tickers = await exchange.fetch_tickers()
            coins = [x['symbol'] for x in sorted(
                tickers.values(), key=lambda y: y['percentage'], reverse=True)[:3]]
            positions = [f"{currency}/USDT" for currency in balance['total'].keys(
            ) if currency not in ['USDT', 'KCS', 'UBXT'] and balance[currency]['total'] != 0.0]
            coins += positions
            await asyncio.gather(*[strategy(exchange, coin, balance) for coin in set(coins)])
        except Exception as e:
            print(e)
        await asyncio.sleep(2)

    await exchange.close()


if __name__ == '__main__':
    asyncio.run(main())
