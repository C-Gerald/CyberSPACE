"""
最小示例策略：EMA 金叉入场 / 死叉离场 + RSI 过滤。

仅用于学习回测与模拟盘（dry-run），不构成任何投资建议。
先回测验证，再考虑小资金实盘。
"""
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy


class EmaCrossStrategy(IStrategy):
    """双均线交叉策略（教学用，参数可自行调整）。"""

    INTERFACE_VERSION = 3

    # 运行周期（也可在命令行用 --timeframe 覆盖）
    timeframe = "5m"

    # 做空（本例只做多）
    can_short = False

    # 止盈：达到 5% 盈利立即平仓（"0": 0.05 表示从入场起任何时刻盈利 5% 即止盈）
    minimal_roi = {"0": 0.05}

    # 止损：-3%
    stoploss = -0.03

    # 不启用移动止损，保持简单
    trailing_stop = False

    # 每根新 K 线只计算一次，避免盘中反复触发
    process_only_new_candles = True

    # 使用策略自带的离场信号
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 指标需要的历史 K 线数量（EMA48、RSI14，留足冗余）
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """计算指标：快慢 EMA + RSI。"""
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=48)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """入场：快线上穿慢线（金叉），且 RSI 未超买。"""
        dataframe.loc[
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_fast"].shift(1) <= dataframe["ema_slow"].shift(1))
            & (dataframe["rsi"] < 70)
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """离场：快线下穿慢线（死叉）。"""
        dataframe.loc[
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"].shift(1)),
            "exit_long",
        ] = 1
        return dataframe
