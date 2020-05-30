# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import time

class MyStrategy(Strategy):
    def initialize(self):
        self._last_evented_time = time.time()
        self._last_ask = self._ask = self._last_bid = self._bid = self._get_board()['mid_price']                               # 現在板の中央値を初期価格とする
        self._ordered_id_list = deque([{}], maxlen=100)       # 発注済みID

    def executions(self,recept_data):
        start = time.time()
        for i in recept_data:
            # ask / bid の更新
            self._last_ask , self._last_bid = self._ask , self._bid
            if i['side']=='BUY' : self._ask = int(i['price'])
            else                : self._bid = int(i['price'])

            if( self._last_evented_time + self._strategy_config['interval'] < start and # 前回のオーダーからinterval_time秒以上経っている
                self._strategy_config['spread'] < self._ask-self._bid  and              # スプレッドが閾値以上開いている
                (not self.order_signal_event.is_set()) ):                               # 前回のイベントが処理済み

                # 買いによってaskが上昇していていればエントリー
                if i['side'] =='BUY' and self._ask > self._last_ask :
                    self._order_price = self._ask
                    self._order_side = 'BUY'
                    self._last_evented_time = start
                    self.order_signal_event.set()

                # 売りによってbidが下降していればエントリー
                elif i['side'] =='SELL' and self._bid < self._last_bid :
                    self._order_price = self._bid
                    self._order_side = 'SELL'
                    self._last_evented_time = start
                    self.order_signal_event.set()

    def realtime_logic(self):
        # 現在の板情報から板の厚みを考慮してエントリーポイントを決定
        board_price = self._get_effective_tick( size_thru=self._strategy_config['depth'], startprice=self._order_price )

        id = ''
        if self.current_pos<=self._strategy_config['max_lot'] and self._order_side == 'BUY' :
            responce = self._limit_buy( price=board_price['bid'], size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        if self.current_pos>=-self._strategy_config['max_lot'] and self._order_side == 'SELL' :
            responce = self._limit_sell( price=board_price['ask'], size=self._strategy_config['lotsize'] )
            if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        # オーダーした場合にはidをdictに保存しておく
        if id!='' : self._ordered_id_list[-1][id]=1

    def loss_cut_check(self):
        while len(self._ordered_id_list)>self._strategy_config['cancel_time'] : # cancel_time 個以上のキューが有れば、
            id_dict =  self._ordered_id_list.popleft()                          # キューから一番古いものを取り出して
            if id_dict!={} :                                                   # オーダーデータがあればキャンセル実行
                for id,val in id_dict.items() :     # dictに入っているid全てを
                    self._cancel_childorder( id )   # 順次キャンセル発行

        # 時間経過管理用のキューをシフト
        self._ordered_id_list.append( {} )

        # 稼働状況のログ
        self._logger.info( '                      LTP:{:.0f}   Profit:{:>+8.0f} Position:{:>7.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                    self.ltp, self.current_profit, self.current_pos, self.api_count, self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        return False