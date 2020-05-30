# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import numpy
import talib

class MyStrategy(Strategy):

    def initialize(self):
        self._last_candle = 0
        self.current_ema = 0

    def logic(self):
        # 初回はcryptowatchから取得しておく
        if self._last_candle==0:
            # strategy.yamlファイルにcryptowatch_candleを指定すると、継続的に読み続けるので
            # yamlファイルでは指定せずここで直接指定して取得ルーチンを直接コール (self.fetch_cryptowatch_candleはv7.02以降でサポート)
            self.fetch_cryptowatch_candle( minutes=1 )
            self.cw_candles = self.cryptowatch_candle

        # ローソク足が変化したときだけ取引
        if self._last_candle==self.candle_date: return
        self._last_candle=self.candle_date

        # Cryptowatchでのローソク足をつなぐために2本以上は必要
        if len(self.close)<2 : return

        # Cryptowatchからの取得分の最後部分と約定履歴から生成したローソク足で被ったものがあればひとつ削除 (Cryptowatchの最後部分は未確定足なので）
        if self.cw_candles.index[-1] == self.candle_date :
            self.cw_candles = self.cw_candles.head(len(self.cw_candles)-1)

        # Cryptowatchからの取得分と約定履歴から生成したものをつなげる（約定履歴から生成したものの先頭は不確定なものがあるので[1:]にて先頭をひとつ削除）
        o = numpy.hstack((numpy.array(self.cw_candles["open"], dtype='f8'), numpy.array(self.open[1:], dtype='f8')))
        h = numpy.hstack((numpy.array(self.cw_candles["high"], dtype='f8'), numpy.array(self.high[1:], dtype='f8')))
        l = numpy.hstack((numpy.array(self.cw_candles["low"],  dtype='f8'), numpy.array(self.low[1:],  dtype='f8')))
        c = numpy.hstack((numpy.array(self.cw_candles["close"],dtype='f8'), numpy.array(self.close[1:],dtype='f8')))

        # talibを用いてemaを計算
        ema = talib.EMA(c, timeperiod=self._strategy_config['period'])
        self.current_ema = ema[-1]

        # EMAをcloseが下から上に抜いた時に買い
        if ema[-2] > c[-2] and ema[-1] < c[-1] :
            # 現在ポジをプラスしてドテン
            self._market_buy( size=self._strategy_config['lotsize']-self.current_pos )

        # EMAをcloseが上から下に抜いた時に売り
        if ema[-2] < c[-2] and ema[-1] > c[-1] :
            # 現在ポジをプラスしてドテン
            self._market_sell( size=self._strategy_config['lotsize']+self.current_pos )

    def loss_cut_check(self):
        if not self.is_backtesting :
            self._logger.info( 'LTP:{:.0f} EMA:{:.0f} Profit:{:>+8.0f}({:+4.0f}) Position:{:.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                self.ltp, self.current_ema, self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))
        return False
