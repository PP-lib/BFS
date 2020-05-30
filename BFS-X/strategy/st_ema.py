# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import numpy
import talib

class MyStrategy(Strategy):

    def initialize(self):
        self._last_candle = 0
        self.current_ema = 0

    def logic(self):
        # �����cryptowatch����擾���Ă���
        if self._last_candle==0:
            # strategy.yaml�t�@�C����cryptowatch_candle���w�肷��ƁA�p���I�ɓǂݑ�����̂�
            # yaml�t�@�C���ł͎w�肹�������Œ��ڎw�肵�Ď擾���[�`���𒼐ڃR�[�� (self.fetch_cryptowatch_candle��v7.02�ȍ~�ŃT�|�[�g)
            self.fetch_cryptowatch_candle( minutes=1 )
            self.cw_candles = self.cryptowatch_candle

        # ���[�\�N�����ω������Ƃ��������
        if self._last_candle==self.candle_date: return
        self._last_candle=self.candle_date

        # Cryptowatch�ł̃��[�\�N�����Ȃ����߂�2�{�ȏ�͕K�v
        if len(self.close)<2 : return

        # Cryptowatch����̎擾���̍Ō㕔���Ɩ�藚�����琶���������[�\�N���Ŕ�������̂�����΂ЂƂ폜 (Cryptowatch�̍Ō㕔���͖��m�葫�Ȃ̂Łj
        if self.cw_candles.index[-1] == self.candle_date :
            self.cw_candles = self.cw_candles.head(len(self.cw_candles)-1)

        # Cryptowatch����̎擾���Ɩ�藚�����琶���������̂��Ȃ���i��藚�����琶���������̂̐擪�͕s�m��Ȃ��̂�����̂�[1:]�ɂĐ擪���ЂƂ폜�j
        o = numpy.hstack((numpy.array(self.cw_candles["open"], dtype='f8'), numpy.array(self.open[1:], dtype='f8')))
        h = numpy.hstack((numpy.array(self.cw_candles["high"], dtype='f8'), numpy.array(self.high[1:], dtype='f8')))
        l = numpy.hstack((numpy.array(self.cw_candles["low"],  dtype='f8'), numpy.array(self.low[1:],  dtype='f8')))
        c = numpy.hstack((numpy.array(self.cw_candles["close"],dtype='f8'), numpy.array(self.close[1:],dtype='f8')))

        # talib��p����ema���v�Z
        ema = talib.EMA(c, timeperiod=self._strategy_config['period'])
        self.current_ema = ema[-1]

        # EMA��close���������ɔ��������ɔ���
        if ema[-2] > c[-2] and ema[-1] < c[-1] :
            # ���݃|�W���v���X���ăh�e��
            self._market_buy( size=self._strategy_config['lotsize']-self.current_pos )

        # EMA��close���ォ�牺�ɔ��������ɔ���
        if ema[-2] < c[-2] and ema[-1] > c[-1] :
            # ���݃|�W���v���X���ăh�e��
            self._market_sell( size=self._strategy_config['lotsize']+self.current_pos )

    def loss_cut_check(self):
        if not self.is_backtesting :
            self._logger.info( 'LTP:{:.0f} EMA:{:.0f} Profit:{:>+8.0f}({:+4.0f}) Position:{:.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                self.ltp, self.current_ema, self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))
        return False
