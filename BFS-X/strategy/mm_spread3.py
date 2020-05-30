# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import time

class MyStrategy(Strategy):

    def initialize(self):
        self._last_ask = self._ask = self._last_bid = self._bid = 0
        if not self.is_backtesting : self._last_evented_time = time.time()
        else :                       self._last_evented_time = 0
        self._order_price = 0
        self._order_side = 'NONE'
        self._ordered_id_list = deque(maxlen=100)  # 100個のキューを用意しておく（適当な数）

    def executions(self,recept_data):
        if not self.is_backtesting : start = time.time()
        else :                       start = recept_data[0]['timestamp']

        # 初回の初期化
        if self._ask == 0 : self._ask = recept_data[0]['price']
        if self._bid == 0 : self._bid = recept_data[0]['price']

        # 約定履歴の処理
        for i in recept_data:
            current_price = int(i['price'])

            self._last_ask, self._last_bid = self._ask, self._bid

            if i['side']=='BUY' : self._ask = current_price
            else:                 self._bid = current_price

            # スプレッド閾値を超えていたら売買イベントをセット
            if( self._last_evented_time + self._strategy_config['interval'] < start and # 前回のオーダーからinterval_time秒以上経っている
                self._strategy_config['spread'] < self._ask-self._bid  and              # スプレッドが閾値以上開いている
                (not self.order_signal_event.is_set()) ):                               # 前回のイベントが処理済み

                if i['side'] =='BUY' :
                    if self._ask > self._last_ask :  # 買いによってaskが上昇していていればエントリー
                        self._order_price = int(self._bid + self._strategy_config['depth'])
                        self._order_side = 'BUY'

                        # 売買イベントをセット
                        self._last_evented_time = start
                        self.order_signal_event.set()
                else:
                    if self._bid < self._last_bid :  # 売りによってbidが下降していればエントリー
                        self._order_price = int(self._ask - self._strategy_config['depth'])
                        self._order_side = 'SELL'

                        # 売買イベントをセット
                        self._last_evented_time = start
                        self.order_signal_event.set()

    def realtime_logic(self):
        id = ''
        # 最大ロットを超えていなければエントリーシグナルにそってエントリー処理
        if self.current_pos<=self._strategy_config['max_lot'] and self._order_side == 'BUY' :
            responce = self._limit_buy( price=self._order_price, size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        if self.current_pos>=-self._strategy_config['max_lot'] and self._order_side == 'SELL' :
            responce = self._limit_sell( price=self._order_price, size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        # オーダーした場合にはidをqueueに保存しておく
        if id!='' : self._ordered_id_list.append(id)

        self._order_side = 'NONE'

        return (id!='')

    def loss_cut_check(self):
        if not self.is_backtesting :
            self._logger.info( '                      LTP:{:.0f}   Profit:{:>+8.0f}({:+4.0f}) Position:{:>7.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                    self.ltp, self.current_profit, self.current_profit_unreal, self.current_pos, self.api_count,
                    self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        # 指定個数以上のオーダーidが有れば、キューから取り出してキャンセル実行
        while len(self._ordered_id_list)>self._strategy_config['max_order_count'] :
            self._cancel_childorder( self._ordered_id_list.popleft() )

        return False
