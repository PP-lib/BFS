#-------------------------------------------------------------------
# オーダーの約定検出をトリガーにして何かアクションを行うbotのコード例です
#-------------------------------------------------------------------

# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
import time
from collections import deque
import numpy as np

class MyStrategy(Strategy):

    def initialize(self):
        self._ask = self._bid = 0
        self._exec_history = deque(maxlen=10000)
        self._exec_history_std = 100
        if not self.is_backtesting : self._last_evented_time = time.time()
        else :                       self._last_evented_time = 0
        self._order__buy_price = self._order__sell_price = 0

    def executions(self,recept_data):
        start = time.time()

        # 初回の価格初期化
        if self._ask == 0 : self._ask = recept_data[0]['price']
        if self._bid == 0 : self._bid = recept_data[0]['price']

        # 約定履歴の処理
        for i in recept_data:
            current_price = int(i['price'])
            self._exec_history.append(current_price)

            if i['side']=='BUY' : self._ask = current_price
            else                : self._bid = current_price

            if( self._last_evented_time + self._strategy_config['interval'] < start and    # 前回のオーダーからinterval_time秒以上経っている
                (not self.order_signal_event.is_set()) ):                                  # 前回のイベントが処理済み

                # 直近(期間はwindowで指定)の価格の標準偏差に対してeffectで重みづけをして指値位置を決める
                self._order__sell_price = (self._ask+self._bid)/2 + self._exec_history_std * self._strategy_config['effect']
                self._order__buy_price  = (self._ask+self._bid)/2 - self._exec_history_std * self._strategy_config['effect']

                # 現在のポジション量に応じて価格を調整
                if self.current_pos>0 : self._order__buy_price  -= (self.current_pos * self._strategy_config['penalty'])
                if self.current_pos<0 : self._order__sell_price -= (self.current_pos * self._strategy_config['penalty'])

                # 売買イベントをセット
                self._last_evented_time = start
                self.order_signal_event.set()

    def realtime_logic(self):

        if self.execution_event.is_set() :  # もし、約定判定で呼び出された場合には
            self.execution_event.clear()    # セットされたイベントをクリア
            self._update_position()         # 約定履歴からポジションを再計算して
            #---------------------
            # なんらかの処理を行う
            self._logger.info( " Current Position {:>7.3f}  Position Average {:.0f}".format(self.current_pos,self.current_average) )
            #---------------------


        self._logger.info( '                      LTP:{:.0f}   ASK:{:.0f}   BID:{:.0f}   STD:{:.1f}'.format(self.ltp,self._order__sell_price,self._order__buy_price,self._exec_history_std) )

        # 最大ロットを超えていなければエントリー処理
        if self.current_pos<= self._strategy_config['max_lot'] : self._limit_buy(  price=round(self._order__buy_price),  size=self._strategy_config['lotsize'] )
        if self.current_pos>=-self._strategy_config['max_lot'] : self._limit_sell( price=round(self._order__sell_price), size=self._strategy_config['lotsize'] )

    def loss_cut_check(self):
        # このループで直近約定のばらつきを評価
        exec_list = list(self._exec_history)[-min(len(self._exec_history),self._strategy_config['window']):] # 直近のexec履歴からwindow分
        self._exec_history_std = np.array(exec_list).std()

        self._logger.info( '                      LTP:{:.0f}  Profit:{:>+8.0f}({:+4.0f}) Position:{:>7.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                    self.ltp, self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                    self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))
        return False
