# -*- coding: utf-8 -*-
from libs.base_strategy import Strategy
from collections import deque
import time
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

class MyStrategy(Strategy):
    #----------------------------------------------------------------------------
    # 起動時に呼ばれる関数
    #----------------------------------------------------------------------------
    def initialize(self):
        self._ask = self._bid = 0
        self._last_evented_time = time.time()
        self._ordered_id_list = deque(maxlen=100)       # 発注済みID
        self._ordered_id_list.append( {} )
        self._buy_volume_list = deque(maxlen=1000)      # 買いボリューム計算用
        self._buy_volume_list.append(0)
        self._sell_volume_list = deque(maxlen=1000)     # 売りボリューム計算用
        self._sell_volume_list.append(0)

        self.__price_list = deque({},maxlen=100)        # 指標の確認用リスト
        self.__index_rate = deque({},maxlen=10000)      # 指標の結果
        self.__index_delta = deque({},maxlen=10000)     # 指標の結果
        self.__last_minutes = 0

    #----------------------------------------------------------------------------
    # Websocketのon_message内から呼び出される関数
    #----------------------------------------------------------------------------
    def executions(self,recept_data):
        start = time.time()
        
        # 初回の初期化
        if self._ask == 0 : self._ask = recept_data[0]['price']
        if self._bid == 0 : self._bid = recept_data[0]['price']

        # 約定履歴の処理
        for i in recept_data:
            if i['side']=='BUY' :
                self._ask = int(i['price'])
                self._buy_volume_list[-1] += i['size']
            else:
                self._bid = int(i['price'])
                self._sell_volume_list[-1] += i['size']

        # 前回のオーダーからinterval_time秒以上経っていたらイベントをセット
        if( self._last_evented_time + self._strategy_config['interval'] < start and (not self.order_signal_event.is_set()) ):
            self._last_evented_time = start
            self.order_signal_event.set()

    #----------------------------------------------------------------------------
    # self.order_signal_eventが発生したら呼び出される関数
    #----------------------------------------------------------------------------
    def realtime_logic(self):

        # 売りの取引高と買いの取引高の差分を求める
        buy_volume = sum(self._buy_volume_list)
        sell_volume = sum(self._sell_volume_list)
        vol_rate = math.sqrt(buy_volume) - math.sqrt(sell_volume)

        # 指標の妥当性検証用（指標と現在価格と時刻を格納）
        self.__price_list.append( {'price':self.ltp, 'rate':vol_rate, 'time':time.time()} )

        # 稼働状況のログ
        self._logger.info( '            Vol{:+3.1f} LTP:{:.0f} Profit:{:>+7.0f} Pos:{:>7.3f} API:{:>3} Delay:{:>4.0f}ms({:>4.0f}ms) {}'.format(
                    vol_rate, self.ltp, self.current_profit, self.current_pos, self.api_count,
                    self.server_latency, self.server_latency_rate, "" if self.server_health == "NORMAL" else " "+self.server_health ))

        # 売買高の差が指定値以下であればエントリーしない
        if math.fabs(vol_rate) < self._strategy_config['volume_th'] :
            return False

        id = ''
        if vol_rate > 0 :
            # 現在ポジがmaxに近づくにつれて発注サイズを減らしてく
            size = math.tanh(self._strategy_config['lotsize'] * (self._strategy_config['max_lot'] - max(0,self.current_pos)) / self._strategy_config['max_lot'])
            if size > 0.01 :
                responce = self._limit_buy( price=self._bid-self._strategy_config['depth'], size=size )
                if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        if vol_rate < 0 :
            # 現在ポジがmaxに近づくにつれて発注サイズを減らしてく
            size = math.tanh(self._strategy_config['lotsize'] * (self._strategy_config['max_lot'] + min(0,self.current_pos)) / self._strategy_config['max_lot'])
            if size > 0.01 :
                responce = self._limit_sell( price=self._ask+self._strategy_config['depth'], size=size )
                if responce and "JRF" in str(responce) : id = responce['child_order_acceptance_id']

        # オーダーした場合にはidをdictに保存しておく
        if id!='' : self._ordered_id_list[-1][id]=1

        return (id!='')

    #----------------------------------------------------------------------------
    # server_healthに関係なく 1 (秒)ごとに回ってくるので、ロスカットチェックなどはこちらで行う
    # 売買が発生したら戻り値をTrueに　→　emergency_waitのタイマー発動
    #----------------------------------------------------------------------------
    def loss_cut_check(self):
        
        while len(self._ordered_id_list)>self._strategy_config['cancel_time'] : # cancel_time 個以上のキューが有れば、
            id_dict =  self._ordered_id_list.popleft()                          # キューから一番古いものを取り出して
            if id_dict!={} :                                                   # オーダーデータがあればキャンセル実行
                for id,val in id_dict.items() :     # dictに入っているid全てを
                    self._cancel_childorder( id )   # 順次キャンセル発行

        # 時間経過管理用のキューをシフト
        self._ordered_id_list.append( {} )
        self._buy_volume_list.append( 0 )
        self._sell_volume_list.append( 0 )

        while len(self._buy_volume_list)>self._strategy_config['volume_period'] :   # volume_period以上のものは
            info = self._buy_volume_list.popleft()                                  # 取り出して捨てる
        while len(self._sell_volume_list)>self._strategy_config['volume_period'] :  # volume_period以上のものは
            info = self._sell_volume_list.popleft()                                 # 取り出して捨てる


        # 指標の有効性確認（scatter_seconds秒後の価格変動を調査）
        for i in range(len(self.__price_list)):
            info = self.__price_list.popleft()                                     # 一番古いものを取り出して
            if info['time']>time.time()-self._strategy_config['scatter_seconds'] : # scatter_seconds秒経っていなかったら
                self.__price_list.appendleft( info )                               # リストに戻して
                break;                                                             # ループを抜ける
            self.__index_rate.append(info['rate'])            # scatter_seconds秒経っていたら指標と
            self.__index_delta.append(self.ltp-info['price']) # 価格の上下変動を保存

        while len(self.__index_rate)>self._strategy_config['scatter_buff_len'] :   # 保管上限個数以上のものは
            info = self.__index_rate.popleft()                                     # 取り出して捨てる
        while len(self.__index_delta)>self._strategy_config['scatter_buff_len'] :  # 保管上限個数以上のものは
            info = self.__index_delta.popleft()                                    # 取り出して捨てる

        # scatter_plot_interval 分ごとに、散布図をプロットしてdiscordへ送信
        if len(self.__index_rate)>2 and self.__last_minutes != int(time.time()/self._strategy_config['scatter_plot_interval']/60) :
            self.__last_minutes = int(time.time()/self._strategy_config['scatter_plot_interval']/60)
            self.plot_scatter(np.array(self.__index_rate), np.array(self.__index_delta))

        return False


# 散布図と相関係数のプロット---------------------------------------------------------------
# 　参考URL : https://note.mu/ycrypthon/n/n324c550f2830

    def plot_scatter(self, x, returns, normalize=True):
        """
        :param np.ndarray x: 指標
        :param np.ndarray returns: リターン
        :param bool normalize: x をスケーリングするかどうか
        """

        # ログフォルダ内にファイルを作成
        image_file = self._parent._parameters._strategy['log_folder']+str(type(self))[17:-13]+'_rate_delta.png'

        assert(len(x) == len(returns))
        # 正規化
        x = (x - x.mean()) / x.std() if normalize else x
        # 散布図
        plt.plot(x, returns, 'x')
        # 回帰直線
        reg = np.polyfit(x, returns, 1)
        plt.plot(x, np.poly1d(reg)(x), color='c', linewidth=2)
        # 区間平均値
        plt.plot(*_steps(x, returns), drawstyle='steps-mid', color='r', linewidth=2)

        # 相関係数（情報係数）
        ic = np.corrcoef(x, returns)[0, 1]
        plt.title(f'IC={ic:.3f}, y={reg[0]:.3f}x{reg[1]:+.3f}')
        plt.grid()
        plt.savefig(image_file)
        plt.close()

        # discordへ送信 (画像付き)
        self._send_discord( '指標&リターンの相関のグラフ {}samples'.format(len(self.__index_rate)), image_file )

def _steps(x, y):
    int_x = np.round(x)
    ret_x = np.unique(int_x)
    ret_y = []
    for xa in ret_x:
        ret_y.append(np.average(y[int_x == xa]))
    return ret_x, np.array(ret_y)
    


