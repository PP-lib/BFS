# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import talib
import numpy

class MyStrategy(Strategy):
    def initialize(self):
        self._last_candle = 0

    def logic(self):
        # 同じ確定足で何度も取引しないためにcandle_date(秒足)が変わっていなければ取引しない
        if self._last_candle==self.candle_date:
            return False
        self._last_candle=self.candle_date

        # ログに残すほどでも無いのでprint分で表示
        print( '-'*30 )
        print( self.cryptowatch_candle.tail(3) ) # Cryptyowatchから取得したローソク足の直近３足

        # 秒足が必要な長さ溜まっていなければ取引しない
        if len(self.close) <= self._strategy_config['ema_period'] :
            if not self.is_backtesting :
                self._logger.info( 'Waiting candles.  {}/{}'.format(len(self.close),self._strategy_config['ema_period']) )
            return False

        # 作成されているローソク足(分足)から使用したい値をnumpyに格納 　（分足の長さは cryptowatch_candle で指定）
        # open(始値) , high(高値) , low(安値) , close(終値) , volume(出来高) が取得できます
        minutes_close = numpy.array(self.cryptowatch_candle['close'], dtype='f8')

        # talibを用いてemaの計算
        minutes_ema = talib.EMA(minutes_close, timeperiod=self._strategy_config['ema_period'])

        # 作成されているローソク足(秒足)から使用したい値をnumpyに格納 　（秒足の長さは timescale で指定）
        # self.open(始値) , self.high(高値) , self.low(安値) , self.close(終値) , self.volume(出来高) が取得できます
        seconds_close = numpy.array(self.close, dtype='f8')

        # talibを用いてemaの計算
        seconds_ema = talib.EMA(seconds_close, timeperiod=self._strategy_config['ema_period'])

        # 現在の状況ログ表示
        self._logger.info( '[{} LTP:{:.0f}] EMA(sec):{:>7.2f} EMA(min):{:>7.2f} Profit:{:>+8.0f}({:+4.0f}) Position:{:.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
            self.exec_date, self.ltp, seconds_ema[-1], minutes_ema[-1],
            self.current_profit, self.current_profit_unreal, self.current_pos,
            self.api_count, self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        # 秒足が分足よりも上にあって、ノーポジまたはマイナスポジなら買い（現在ポジを足してドテン買い）
        if self.current_pos<=0 and seconds_ema[-1] > minutes_ema[-1] :
            self._market_buy( size=(self._strategy_config['lotsize']-self.current_pos) )
            return True

        # 秒足が分足よりも下にあって、ノーポジまたはプラスポジなら売り（現在ポジを足してドテン売り）
        if self.current_pos>=0 and seconds_ema[-1] < minutes_ema[-1] :
            self._market_sell( size=(self._strategy_config['lotsize']+self.current_pos) )
            return True

        return False

    def loss_cut_check(self):
        return False

