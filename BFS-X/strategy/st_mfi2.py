# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import talib as ta
import numpy as np
import math
import time

class MyStrategy(Strategy):

    def initialize(self):
        self._last_candle = 0
        self._ordered_id_list = deque(['']*3, maxlen=3)  # logic_loop_periodが5であれば、発注後5*3=15秒でキャンセル発行

    def logic(self):
        # 同じ確定足で何度も取引しないためにcandle_dateが変わっていなければ取引しない
        if self._last_candle==self.candle_date:
            return False
        self._last_candle=self.candle_date

        if len(self.close) <= self._strategy_config['mfi_period'] :
            if not self.is_backtesting :
                self._logger.info( 'Waiting candles.  {}/{}'.format(len(self.close),self._strategy_config['mfi_period']) )
            return False

        id = ''
        # 指数の計算
        h = np.array(self.high)
        l = np.array(self.low)
        c = np.array(self.close)
        v = np.array(self.volume)
        mfi = ta.MFI(h, l, c, v, self._strategy_config['mfi_period'])*2-100

        if not self.is_backtesting :
            self._logger.info( '[{} LTP:{:.0f}] MFI:{:>7.2f} B/S:{:>+4.2f} Profit:{:>+8.0f}({:+4.0f}) Position:{:.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                self.exec_date, self.ltp, mfi[-1], self.vol_rate(), self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        # MAX_LOTに近づくと指値を離して約定しづらくする
        buyprice  = self.ltp - max(0,int(self._strategy_config['position_slide']*self.current_pos/self._strategy_config['max_lot']))-self._strategy_config['depth']
        sellprice = self.ltp - min(0,int(self._strategy_config['position_slide']*self.current_pos/self._strategy_config['max_lot']))+self._strategy_config['depth']

        # 閾値を超えていれば売買
        if self.current_pos<=self._strategy_config['max_lot'] and mfi[-1] < -self._strategy_config['mfi_limit'] :
            responce = self._limit_buy( price=buyprice, size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']
        if self.current_pos>=-self._strategy_config['max_lot'] and mfi[-1] > self._strategy_config['mfi_limit'] :
            responce = self._limit_sell( price=sellprice, size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']
        self._ordered_id_list.append( id )

        # 一定時間が経ったオーダーをキャンセル発行
        if self._ordered_id_list[0]!='' :
            self._cancel_childorder( self._ordered_id_list[0] )

        return (id!='')

    def loss_cut_check(self):

        # マイナスポジで大きな買いが入った場合には成でクローズ
        if self.current_pos<0 and self.vol_rate()>self._strategy_config['volume_limit'] :
            return self._close_position()

        # プラスポジで大きな売りが入った場合には成でクローズ
        if self.current_pos>0 and self.vol_rate()<-self._strategy_config['volume_limit'] :
            return self._close_position()

        # 現在の建玉を表示
        positions = self._get_positions()
        close_size = 0
        current_time = time.time()
        if positions : self._logger.info( '-'*30 )
        for p in positions:
            self._logger.info( '                      {:>3.0f}sec : {}'.format(current_time-p['timestamp'],p) )
            if p['timestamp'] < current_time-self._strategy_config['position_close'] :
                close_size += p['size']    # 指定時間が過ぎた建玉をカウント

        # クローズすべき建玉が有れば
        if close_size!= 0 : 
            if self.current_pos>0 : #現在のポジションがロングなら
                self._market_sell( size=round(close_size,8) )
            else:                   #現在のポジションがショートなら
                self._market_buy( size=round(close_size,8) )

        return False

    def vol_rate(self):
        vol_rate = math.fabs(math.sqrt(self.buy_volume[-1]) - math.sqrt(self.sell_volume[-1]))
        if self.buy_volume[-1] < self.sell_volume[-1] :
            vol_rate = -vol_rate
        return vol_rate
