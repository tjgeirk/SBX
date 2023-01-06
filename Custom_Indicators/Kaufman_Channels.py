from pandas import DataFrame as dataframe
from ta import volatility, momentum

def adaptiveBands(window=20, atrs=2) -> dataframe:
    df = {}
    atr = volatility.average_true_range(
        data()['high'], data()['low'], data()['close'], window)
    df['middle'] = momentum.kama(data()['close'], window)
    df['upper'] = df['middle']+(atrs*atr)
    df['lower'] = df['middle']-(atrs*atr)
    return dataframe(df)
