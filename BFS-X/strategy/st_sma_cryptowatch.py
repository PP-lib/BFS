# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import numpy
import talib
import copy

class MyStrategy(Strategy):

    def initialize(self):
        self._last_candle = 0
        self.current_short_sma = 0
        self.current_long_sma = 0

    def logic(self):
        # cryptowatchから取得 (最後のは未確定なので捨てる）
        cw_candles = copy.deepcopy(self.cryptowatch_candle[:-1])

        # CryptoWatchから取得したローソク足が前回と変わっていなかったら何もせずに終了
        if self._last_candle == cw_candles.index[-1] : return
        self._last_candle = cw_candles.index[-1]

        # Cryptowatchからの取得ローソク足からnumpy配列を生成
        c = numpy.array(cw_candles["close"],dtype='f8')

        # talibを用いてsmaを計算
        short_sma = talib.SMA(c, timeperiod=self._strategy_config['short_sma'])
        long_sma = talib.SMA(c, timeperiod=self._strategy_config['long_sma'])
        self.current_short_sma = short_sma[-1]
        self.current_long_sma = long_sma[-1]

        # 買いエントリーの条件
        if( self.current_pos <= 0 and
            long_sma[-1]-long_sma[-2] < long_sma[-1]*self._strategy_config['trend_filter'] and
            long_sma[-1] > long_sma[-2] and
            long_sma[-1] < short_sma[-1] and
            long_sma[-2] > short_sma[-2] ) :
            self._market_buy( size=self._strategy_config['lotsize']-self.current_pos )

        # 買いクローズの条件
        elif( self.current_pos > 0 and short_sma[-2] > short_sma[-1] ) :
            self._close_position( )

        # 売りエントリーの条件
        if( self.current_pos >= 0 and
            long_sma[-2]-long_sma[-1] < long_sma[-1]*self._strategy_config['trend_filter'] and
            long_sma[-1] < long_sma[-2] and
            long_sma[-1] > short_sma[-1] and
            long_sma[-2] < short_sma[-2] ) :
            self._market_sell( size=self._strategy_config['lotsize']+self.current_pos )

        # 売りクローズの条件
        elif( self.current_pos < 0 and short_sma[-2] < short_sma[-1] ) :
            self._close_position( )

    def loss_cut_check(self):
        if not self.is_backtesting :
            self._logger.info( 'LTP:{:.0f} short_sma:{:.0f} long_sma:{:.0f} Profit:{:>+8.0f}({:+4.0f}) Position:{:.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                self.ltp, self.current_short_sma, self.current_long_sma, self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))
        return False
