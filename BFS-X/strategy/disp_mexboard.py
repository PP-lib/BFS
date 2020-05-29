# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from threading import Thread, Lock
import json
import websocket
from sortedcontainers import SortedDict
import time

class MyStrategy(Strategy):

    def initialize(self):
        self.last_ask = 0

        # Mexの板情報取得用
        self.lock = Lock()       # 板情報の更新中ロック
        self.bids = SortedDict() # 板情報を格納
        self.asks = SortedDict() # 板情報を格納
        mex_board = WebsocketMexBoard(self, self._logger, 'orderBookL2_25')

    def executions(self,recept_data):
        return

    def realtime_logic(self):
        if len(self.asks)!=0 and len(self.bids)!=0 :

            with self.lock: # アクセス中にwebsocketで更新されないように排他的ロック

                # best_ask/best_bidの上下5つの板サイズの合計
                ask5 = sum([s for i, [p, s] in self.asks.items()[-5:]])
                buy5 = sum([s for i, [p, s] in self.bids.items()[:5]])

                # 上下5つの板情報を表示
                price_txt = '    ask5     '
                size_txt = '({:^9}) '.format(ask5)
                for i, [p, s] in self.asks.items()[-5:]:
                    price_txt += '{:^9.1f} '.format(p)
                    size_txt += '{:^9} '.format(s)
                price_txt += '/  '
                size_txt += ' / '
                for i, [p, s] in self.bids.items()[:5]:
                    price_txt += '{:^9.1f} '.format(p)
                    size_txt += '{:^9} '.format(s)
                price_txt += '   buy5'
                size_txt += '({:^9})'.format(buy5)

                # best_ask/best_bid価格が変化したら
                if self.last_ask != self.asks.items()[-1][1][0] :
                    self.last_ask = self.asks.items()[-1][1][0]
                    print( '' )
                    print( price_txt )
                    print( '-'*120 )

                print( size_txt )
        return False

    def loss_cut_check(self):
        return False


# Mexの板情報をwebsocketで取得するクラス
class WebsocketMexBoard(object):
    def __init__(self,parent,logger,order_book):
        self._parent= parent
        self._logger = logger
        self._order_book = order_book
        self.startWebsocket()
    def startWebsocket(self):
        def on_open(ws):
            self._logger.info("MEX Websocket connected")
        def on_error(ws, error):
            self._logger.error(error)
        def on_close(ws):
            self._logger.info("MEX Websocket closed")
        def run(ws):
            while True:
                ws.run_forever()
                time.sleep(1)
        def on_message(ws, message):
            message = json.loads(message)
            if 'table' not in message or message['table'] != self._order_book:
                return
            action = message['action']
            data = message['data']
            with self._parent.lock:
                if action=='partial':
                    bids, asks = SortedDict(), SortedDict() # 空のSortedDictを作って
                    for d in data:                          # すべてのdataを突っ込む
                        idx,side,size,price = d['id'],d['side'],d['size'],float(d['price'])
                        if side == 'Buy':    bids[idx] = [price, size]
                        elif side == 'Sell': asks[idx] = [price, size]
                    self._parent.bids, self._parent.asks = bids, asks
                elif action=='insert':
                    for d in data:                          # すべてのdataを突っ込む
                        idx,side,size,price = d['id'],d['side'],d['size'],float(d['price'])
                        if side == 'Buy':    self._parent.bids[idx] = [price, size]
                        elif side == 'Sell': self._parent.asks[idx] = [price, size]
                elif action == 'update':
                    for d in data:                          # すべてのdataを更新
                        idx,side,size = d['id'],d['side'],d['size']
                        if side == 'Buy':    self._parent.bids[idx][1] = size
                        elif side == 'Sell': self._parent.asks[idx][1] = size
                elif action == 'delete':
                    for d in data:                          # すべてのdataを削除
                        idx,side = d['id'],d['side']
                        if side == 'Buy':    del self._parent.bids[idx]
                        elif side == 'Sell': del self._parent.asks[idx]
                # イベントをセット(realtime_logicが呼び出される)
                self._parent.order_signal_event.set()
        ws = websocket.WebSocketApp( "wss://www.bitmex.com/realtime?subscribe="+self._order_book+":XBTUSD",
            on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close )
        websocketThread = Thread(target=run, args=(ws, ))
        websocketThread.start()
