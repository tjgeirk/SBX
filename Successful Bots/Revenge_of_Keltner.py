import ta.volatility as vol
import pandas as pd
import ccxt.async_support as ccxt
import asyncio
import time

exchange = ccxt.kucoinfutures({
    'apiKey': '',
    'secret': '',
    'password': '',
    'adjustForTimeDifference': True,
})

PAIRLIST_LENGTH = 5
TIMEFRAME = '15m'
MAX_LEVERAGE = 5
INITIAL_RISK = 0.01


async def get_price_data(exchange, symbol, timeframe):
    ohlcvs = await exchange.fetch_ohlcv(symbol, timeframe)
    columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = pd.DataFrame(ohlcvs, columns=columns)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
    df.set_index('Timestamp', inplace=True)
    return df


async def set_targets(exchange, symbol, timeframe, positions):
    price_data = await get_price_data(exchange, symbol, timeframe)
    keltner_channel = vol.KeltnerChannel(
        high=price_data['High'], low=price_data['Low'], close=price_data['Close'], window=20, window_atr=10)
    price_data['upper_band'] = keltner_channel.keltner_channel_hband()
    price_data['middle_band'] = keltner_channel.keltner_channel_mband()
    price_data['lower_band'] = keltner_channel.keltner_channel_lband()

    last_close = price_data['Close'].iloc[-1]
    last_middle_band = price_data['middle_band'].iloc[-1]
    last_lower_band = price_data['lower_band'].iloc[-1]
    last_upper_band = price_data['upper_band'].iloc[-1]
    trend_direction = 'Up' if last_close > last_middle_band else 'Down'
    is_trending = abs(
        last_close - last_middle_band) > abs(last_middle_band - last_lower_band)

    if is_trending:
        buy_target, sell_target = (last_middle_band, last_upper_band) if trend_direction == 'Up' else (
            last_lower_band, last_middle_band)
    else:
        buy_target, sell_target = (last_lower_band, last_upper_band)

    await place_orders(buy_target, sell_target, symbol, exchange, positions)


async def place_orders(buy_target, sell_target, symbol, exchange, positions):
    balance = (await exchange.fetch_balance())['free']['USDT']
    lever = min(exchange.markets[symbol]['info']['maxLeverage'], MAX_LEVERAGE)
    long_qty = max(1, (balance * lever / buy_target) * INITIAL_RISK)
    short_qty = max(1, (balance * lever / sell_target) * INITIAL_RISK)
    side = [x['side'] for x in positions if x['symbol'] == symbol]

    if 'long' in side:
        await exchange.create_limit_sell_order(symbol, 1, sell_target, {'closeOrder': True})
        await exchange.create_stop_limit_order(symbol, 'buy', long_qty, buy_target, buy_target, {'leverage': lever})
    elif 'short' in side:
        await exchange.create_limit_buy_order(symbol, 1, buy_target, {'closeOrder': True})
        await exchange.create_stop_limit_order(symbol, 'sell', short_qty, sell_target, sell_target, {'leverage': lever})
    else:
        await exchange.create_stop_limit_order(symbol, 'buy', long_qty, buy_target, buy_target, {'leverage': lever})
        await exchange.create_stop_limit_order(symbol, 'sell', short_qty, sell_target, sell_target, {'leverage': lever})


async def process_open_orders(coin):
    now = time.time()
    open_orders = await exchange.fetch_open_orders(coin)
    for order in open_orders:
        if now - order['timestamp'] / 1000 > 15:
            try:
                await exchange.cancel_order(order['id'])
            except ccxt.BaseError:
                pass


async def main():
    while True:
        markets = await exchange.load_markets()
        balance = await exchange.fetch_balance()
        markets = sorted(markets.values(),
                         key=lambda x: x['info']['priceChgPct'], reverse=True)
        positions = await exchange.fetch_positions()
        coins = [x['symbol'] for x in markets][:PAIRLIST_LENGTH]
        coins += [x['symbol'] for x in positions]
        tasks = [asyncio.create_task(set_targets(
            exchange, coin, TIMEFRAME, positions)) for coin in coins]
        tasks += [asyncio.create_task(process_open_orders(coin))
                  for coin in coins]
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(e)
