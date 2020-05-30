# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import numpy
from copy import deepcopy
from collections import deque

class MyStrategy(Strategy):
    def initialize(self):
        self.last_high = self.last_low = 0
        self.candle_high = self.candle_low = 0
        self.last_pos = None
        self._last_candle = 0

    def logic(self):

        # cryptowatchから取得 (最後のは未確定なので捨てる）
        cw_candles = deepcopy(self.cryptowatch_candle[:-1])

        # ポジがあるときにはローソク足が変化したときだけ取引
        if self._last_candle == cw_candles.index[-1] and len(self.parentorder_ordered_list)>0 : return
        self._last_candle = cw_candles.index[-1]

        # period区間の高値と安値を計算
        self.candle_high = numpy.array(cw_candles["high"],dtype='f8')[-self._strategy_config['period']:].max()
        self.candle_low  = numpy.array(cw_candles["low"],dtype='f8')[-self._strategy_config['period']:].min()

        # 現在ポジが変わった時か上方向チャンネルが変化したとき
        if self.current_pos <= 0 and (self.last_pos != self.current_pos or self.last_high != self.candle_high) :

            if self.current_pos != 0 and len(self.parentorder_ordered_list)>0 :
                # 現在ポジがある場合には既存のオーダーを全キャンセルしてから(次のループで)オーダーを発行
                ordered_list = deepcopy( self.parentorder_ordered_list )
                for id in ordered_list : self._cancel_parentorder( id )
                self.candle_high = self.candle_low = 0
                return False

            self.last_pos = self.current_pos
            id = ''
            responce = self._parentorder( [self.order(type="STOP_LIMIT", side="BUY", size=self._strategy_config['lotsize']-self.current_pos, trigger=self.candle_high, price=self.candle_high)] )
            self._logger.info( "Set STOP_LIMIT ORDER : BUY {:.0f}  : {}".format( self.candle_high,responce ) )
            if responce and "JRF" in str(responce) : id = responce['parent_order_acceptance_id']
            if id!='' : self.last_high = self.candle_high  # オーダー成功

        # 現在ポジが変わった時か下方向チャンネルが変化したとき
        if self.current_pos >= 0 and (self.last_pos != self.current_pos or self.last_low != self.candle_low) :

            if self.current_pos != 0 and len(self.parentorder_ordered_list)>0 :
                # 現在ポジがある場合には既存のオーダーを全キャンセルしてから(次のループで)オーダーを発行
                ordered_list = deepcopy( self.parentorder_ordered_list )
                for id in ordered_list : self._cancel_parentorder( id )
                self.candle_high = self.candle_low = 0
                return False

            self.last_pos = self.current_pos
            id = ''
            responce = self._parentorder( [self.order(type="STOP_LIMIT", side="SELL", size=self._strategy_config['lotsize']+self.current_pos, trigger=self.candle_low, price=self.candle_low)] )
            self._logger.info( "Set STOP_LIMIT ORDER : SELL {:.0f}  : {}".format( self.candle_low,responce ) )
            if responce and "JRF" in str(responce) : id = responce['parent_order_acceptance_id']
            if id!='' : self.last_low = self.candle_low  # オーダー成功

        if self.current_pos > 0 : self.candle_high = 0
        if self.current_pos < 0 : self.candle_low = 0

        return False

    def loss_cut_check(self):
        self._logger.info( '          (HIGH:{:>7.0f} / LOW:{:>7.0f})   LTP:{:>7.0f} Total pnl:{:>+8.0f} (Unreal pnl:{:+4.0f}) Position:{:>7.3f} {}'.format(
                self.candle_high, self.candle_low, self.ltp, self.current_profit, self.current_profit_unreal, self.current_pos,
                "" if self.server_health == "NORMAL" else " "+self.server_health ))

        return False

