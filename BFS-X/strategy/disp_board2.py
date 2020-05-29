# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy

class MyStrategy(Strategy):
    #----------------------------------------------------------------------------
    # Websocketのon_message内から呼び出される関数
    #----------------------------------------------------------------------------
    def executions(self,recept_data):
        return

    #----------------------------------------------------------------------------
    # 板情報が更新されたら呼び出される関数
    #----------------------------------------------------------------------------
    def board_updated(self):
        # websocketで貯めている板情報の取得
        board = self._get_board()

        asks10000 = sum([a['size'] for a in board['asks'] if a['price']<board['mid_price']+10000])
        bids10000 = sum([b['size'] for b in board['bids'] if b['price']>board['mid_price']-10000])

        self._logger.info( "ask: {:.3f}btc  mid:{:.0f}   bid: {:.3f}btc".format(asks10000,board['mid_price'],bids10000) )

    #----------------------------------------------------------------------------
    # self.order_signal_eventが発生したら呼び出される関数
    #----------------------------------------------------------------------------
    def realtime_logic(self):
        return


    #----------------------------------------------------------------------------
    # server_healthに関係なく 1 (秒)ごとに回ってくるので、ロスカットチェックなどはこちらで行う
    # 売買が発生したら戻り値をTrueに　→　emergency_waitのタイマー発動
    #----------------------------------------------------------------------------
    def loss_cut_check(self):
        return False
