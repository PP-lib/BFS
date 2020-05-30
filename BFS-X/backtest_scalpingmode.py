# -*- coding: utf-8 -*-

import sys
from libs.base_strategy import Strategy
import importlib.machinery as imm
from collections import deque
import time
from datetime import datetime, timedelta
from dateutil import parser
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib as mpl
import warnings
import numpy as np
import yaml
from logging import getLogger, INFO, StreamHandler, FileHandler
import pandas as pd
pd.set_option('display.expand_frame_repr', False)
warnings.filterwarnings('ignore')
import glob

def setup_logger():
    logger = getLogger(__name__)
    handler = StreamHandler()
    handler.setLevel(INFO)
    logger.setLevel(INFO)
    logger.addHandler(handler)
    return logger


def plot_graph(df, display_time=False, filename='', title='', shared_mem=False, pos=None, pnl=None, price=None, delay=None):

    starttime = time.time()

    # ポジションをPandas SeriesからNumpy Ndarrayへ変換
    pos_values = pos if shared_mem else df.pos.values
    # 損益をPandas SeriesからNumpy Ndarrayへ変換
    pnl_values = pnl if shared_mem else df.pnl.values
    # 価格をPandas SeriesからNumpy Ndarrayへ変換
    price_values = price if shared_mem else df.price.values
    delay_values = delay if shared_mem else df.delay.values

    if display_time:
        history_time = df.exec_date_dt.values
    else:
        history_time = [i for i in range(0, len(price_values))]

    fig = plt.figure()
    fig.autofmt_xdate()
    fig.tight_layout()

    # サブエリアの大きさの比率を変える
    gs = mpl.gridspec.GridSpec(nrows=3, ncols=1, height_ratios=[4, 4, 2])
    ax = plt.subplot(gs[0])  # 0行0列目にプロット
    ax.tick_params(labelbottom=False)
    bx2 = plt.subplot(gs[1])  # 1行0列目にプロット
    if not display_time:
        bx2.tick_params(labelbottom=False)
    cx = plt.subplot(gs[2])  # 2行0列目にプロット
    cx.tick_params(labelbottom=False)

    # グラフタイトル
    if title != '':
        fig.suptitle(title, fontsize=9)

    # 上段のグラフ
    ax.set_ylim([min(price_values) - 5, max(price_values) + 5])
    ax.plot(history_time, price_values, label="market price")

    # 中段のグラフ
    bx2.plot(history_time, delay_values, color='green')
    bx2.set_ylim(2, 10)
    bx = bx2.twinx()

    if display_time:
        bx.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H'))
    bx.set_ylim([min(pnl_values) - 5, max(pnl_values) + 5])
    bx.plot(history_time, pnl_values, color='r', label="profit")

    # 下段のグラフ
    cx.set_ylim([min(pos_values) * 1.1, max(pos_values) * 1.1])
    cx.plot(history_time, pos_values, label="position")
    cx.hlines(
        y=0, xmin=history_time[0], xmax=history_time[-1], colors='k', linestyles='dashed')

    # 凡例
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = bx.get_legend_handles_labels()
    h3, l3 = cx.get_legend_handles_labels()
    ax.legend(h1, l1, loc='upper left', prop={'size': 8})
    bx.legend(h2, l2, loc='upper left', prop={'size': 8})
    cx.legend(h3, l3, loc='upper left', prop={'size': 8})

    ax.grid(linestyle=':')
    bx.grid(linestyle=':')
    cx.grid(linestyle=':', which='minor')

    if display_time:
        for i, item in enumerate(bx.get_xticklabels()):
            fontsize = 6
            item.set_fontsize(fontsize)

    if filename != '':
        plt.savefig(filename)
    else:
        plt.show()
    plt.close()

    print("Plot profit graph : {:.3f}sec".format(time.time() - starttime))


def format_date(date_line):
    try:
        if len(date_line) == 19:
            date_line = date_line + '.0'
        dt = datetime(int(date_line[0:4]), int(date_line[5:7]), int(date_line[8:10]), int(
            date_line[11:13]), int(date_line[14:16]), int(date_line[17:19]), int(date_line[20:26]), )
    except:
        exec_date = date_line.replace('T', ' ')
        dt = parser.parse(exec_date)

    return dt


def csvLoad(logger, filename):
    df = pd.read_csv('./'+filename, names=('exec_date', 'side',
                                           'price', 'size', 'id', 'latency'))  # CSVファイル読み込み
    df = df.drop(
        df.index[df.exec_date == 'Connection is already closed.']).dropna()  # 不要行の除去
    df['pos'] = 0.0  # ポジションを初期化
    df['pnl'] = 0.0  # 損益を初期化
    df['delay'] = 0.0
    df['timestamp'] = 0.0

    logger.info('loaded ['+filename+'] : '+str(len(df))+' executions')
    return df


def load_cvs_files(logger, config):
    starttime = time.time()
    if 'execution_files' not in config :
        file_list = glob.glob(config['data_folder']+"*.csv" )
        if not file_list :
            file_list = glob.glob(config['data_folder']+"*.pack" )
        bFirst = True
        for file in sorted(file_list):
            if bFirst:
                df = csvLoad(logger, file)
                bFirst = False
            else:
                df = df.append(csvLoad(logger, file))
    else:
        df = csvLoad(logger, config['data_folder'] +
                     config['execution_files'][0]['file'])
        for i in range(len(config['execution_files'])-1):
            df = df.append(
                csvLoad(logger, config['data_folder']+config['execution_files'][i+1]['file']))

    logger.info('total executions = {}'.format(len(df)))
    print("Loaded CSV files : {:.3f}sec".format(time.time() - starttime))

    starttime = time.time()
    exec_date_values = df.exec_date.values  # 約定時刻をPandas SeriesからNumpy Ndarrayへ変換
    timestamp_values = df.timestamp.values
    delay_values = df.delay.values
    latency_values = df.latency.values
    before30sec = 0

    # datetimeを保持しておく
    df['exec_date_dt'] = None
    datetimes = df.exec_date_dt.values

    for i in range(0, len(df)):
        exec_date = exec_date_values[i]

        # datetimeへ変換
        now_datetime = format_date(exec_date)
        datetimes[i] = now_datetime

        # タイムスタンプへ変換
        now_time = now_datetime.timestamp()

        # 保存
        timestamp_values[i] = now_time

        # 直近30秒の約定数をもとに遅延を推測する
        k = before30sec
        for j in range(k, i):
            if now_time-timestamp_values[j] > 30:
                before30sec = j
            else:
                break
        delay_values[i] = (i-before30sec)/500

        # 直近30秒の約定数をもとに遅延を推測する
#        delay_values[i] = latency_values[i]

    print("Convert to timestamp : {:.3f}sec".format(time.time() - starttime))

    return df


market_buy = 10000000
market_sell = -10000000


# バックテスト用クラス
class backtest:

    def __init__(self, logger, config):
        self._logger = logger
        self._config = config
        self._delay = self._config['delay']
        # apiアクセス回数カウンター(300秒の累積アクセス数)
        self.api_counter = deque([0]*300, maxlen=300)
        self._id_count = 1000

        # strategy configファイル読み込み
        strategy_config_file = self._config['strategy_yaml']
        self.strategy_config = yaml.safe_load(
            open(strategy_config_file, 'r', encoding='utf-8_sig'))
        logger.info("Load strategy configfile: config = {}".format(
            strategy_config_file))

        # 動的に MyStrategy を読み込んでクラスを上書きする
        strategy_py_file = self._config['strategy_py']
        module = imm.SourceFileLoader(
            'MyStrategy', strategy_py_file).load_module()
        logger.info(
            "Load MyStrategy class dynamically: module={}".format(module))
        strategy_class = getattr(module, 'MyStrategy')
        strategy = strategy_class(logger=self._logger, parent=self)
        logger.info('Succeeded setup strategy. logic={}, class={}'.format(
            self._config['strategy_py'], type(strategy)))
        self._strategy = strategy
        self._strategy.set_strategy_config(self.strategy_config['parameters'])

        # 初回の初期化動作
        self.initialize_func = None
        try:
            self.initialize_func = self._strategy.initialize
        except:
            pass
        if self.initialize_func != None:
            self._strategy.initialize()

        self._logic_loop_period = self.strategy_config['logic_loop_period']

        # SEC秒足のローソク足
        self._open = deque(
            maxlen=self.strategy_config['numOfCandle'])   # SEC秒足の始値
        self._high = deque(
            maxlen=self.strategy_config['numOfCandle'])   # SEC秒足の高値
        self._low = deque(
            maxlen=self.strategy_config['numOfCandle'])    # SEC秒足の安値
        self._close = deque(
            maxlen=self.strategy_config['numOfCandle'])  # SEC秒足の終値
        self._volume = deque(maxlen=self.strategy_config['numOfCandle'])
        self._buy_volume = deque(maxlen=self.strategy_config['numOfCandle'])
        self._sell_volume = deque(maxlen=self.strategy_config['numOfCandle'])

    def init_datas_for_multicore(self, dft_timestamp, dft_price, dft_size, dft_side, dft_delay):
        self.dft_timestamp = dft_timestamp
        self.dft_price = dft_price
        self.dft_size = dft_size
        self.dft_side = ['BUY' if s == 1 else 'SELL' for s in dft_side]
        self.dft_delay = dft_delay

    def run(self, dft, multicore=False):

        if 'minutes_to_expire' in self.strategy_config['parameters']:
            self.strategy_config['minutes_to_expire'] = self.strategy_config['parameters']['minutes_to_expire']

        starttime = time.time()

        # ロジックの初期化
        if self.initialize_func != None:
            self._strategy.initialize()

        # 初期化処理
        exec_price = 0  # 取得価格 x サイズ
        hit = 0  # 約定回数

        self._order = []  # 注文格納用の辞書リストorderを初期化
        self._order_start_position = 0
        self._pos = 0  # ポジション情報
        self._pending_time = 0

        # SEC秒足のローソク足
        self._open.clear()   # SEC秒足の始値
        self._high.clear()   # SEC秒足の高値
        self._low.clear()    # SEC秒足の安値
        self._close.clear()  # SEC秒足の終値
        self._volume.clear()
        self._buy_volume.clear()
        self._sell_volume.clear()

        # 指数計算用
        sec_candle = deque(
            maxlen=self.strategy_config['timescale']+1)  # 1秒足のクローズ価格
        self.temp_open = 0
        self.temp_high = 0
        self.temp_low = 1000000000

        # Tempデータフレームの作成とNumpy変換
        if multicore:
            dft['pos'] = np.zeros(len(self.dft_timestamp))
            dft['pnl'] = np.zeros(len(self.dft_timestamp))

            price_values = self.dft_price         # 価格をPandas SeriesからNumpy Ndarrayへ変換
            size_values = self.dft_size        # sizeをPandas SeriesからNumpy Ndarrayへ変換
            side_values = self.dft_side           # sideをPandas SeriesからNumpy Ndarrayへ変換
            exec_date_values = self.dft_timestamp
            timestamp_values = self.dft_timestamp
            delay_values = self.dft_delay

        else:
            price_values = dft.price.values      # 価格をPandas SeriesからNumpy Ndarrayへ変換
            # sizeをPandas SeriesからNumpy Ndarrayへ変換
            size_values = dft['size'].values
            side_values = dft.side.values        # sideをPandas SeriesからNumpy Ndarrayへ変換
            exec_date_values = dft.exec_date.values  # 約定時刻をPandas SeriesからNumpy Ndarrayへ変換
            timestamp_values = dft.timestamp.values
            delay_values = dft.delay.values

        pos_values = dft.pos.values       # ポジションをPandas SeriesからNumpy Ndarrayへ変換
        self.pnl_values = dft.pnl.values  # 損益をPandas SeriesからNumpy Ndarrayへ変換

        previous_second = int(timestamp_values[0])  # 最初の時刻の秒
        last_logic_second = int(
            timestamp_values[0]/self.strategy_config['timescale'])*self.strategy_config['timescale']  # 最初の時刻の秒
        last_candle_second = int(
            timestamp_values[0]/self.strategy_config['timescale'])*self.strategy_config['timescale']  # 最初の時刻の秒
        self.buy_size_total = 0
        self.sell_size_total = 0
        self._next_candle_date = exec_date_values[0]
        self._candle_date = exec_date_values[0]
        self._ltp = self._best_ask = self._best_bid = price_values[0]

        # START時点からEND時点までのループ
        for i in range(0, len(price_values)):

            self._exec_date = exec_date_values[i]  # 最終約定時刻
            self.now_time = timestamp_values[i]

            self.busy_rate = delay_values[i]

            # ローソク足の生成
            self._ltp = price_values[i]
            if self.temp_open == 0:
                self.temp_open = self._ltp
            self.temp_high = max(price_values[i], self.temp_high)
            self.temp_low = min(price_values[i], self.temp_low)

            self.now_second = int(self.now_time)  # 最終時刻の秒

            if previous_second != self.now_second:
                self.api_counter.append(0)  # apiカウンターを1秒ごとにシフトさせる
                # 秒が変わったところで、直前の価格を秒足のクローズ価格とする
                sec_candle.append(price_values[i-1])

                # 前回の売買判断から経過した秒数
                self.elapsed_time_from_logic = self.now_time-last_logic_second
                self.elapsed_time_from_candle = self.now_time-last_candle_second

                # 前回の売買判断からlogic_loop_period秒以上経過していたら(秒足がlogic_loop_period本溜まったら)売買判断
                if self.elapsed_time_from_logic >= self._logic_loop_period and len(sec_candle) > self._logic_loop_period:

                    # 前回の売買判断からtimescale秒以上経過していたら(秒足がtimescale本溜まったら)ローソク足を閉じる
                    if self.elapsed_time_from_candle >= self.strategy_config['timescale'] and len(sec_candle) > self.strategy_config['timescale']:

                        self._open.append(self.temp_open)
                        self._high.append(self.temp_high)
                        self._low.append(self.temp_low)
                        # timescale秒足のクローズ価格
                        self._close.append(sec_candle[-1])
                        self._candle_date = self._next_candle_date

                        self.temp_high = self._ltp
                        self.temp_low = self._ltp
                        self.temp_open = self._ltp

                        self._volume.append(
                            round(self.buy_size_total+self.sell_size_total, 8))
                        self._buy_volume.append(round(self.buy_size_total, 8))
                        self._sell_volume.append(
                            round(self.sell_size_total, 8))
                        self.buy_size_total = 0
                        self.sell_size_total = 0

                        self._next_candle_date = self._exec_date

                        last_candle_second = int(
                            self.now_time/self.strategy_config['timescale'])*self.strategy_config['timescale']

                    last_logic_second = int(
                        self.now_time/self._logic_loop_period)*self._logic_loop_period

                    if self._pending_time < self.now_time:

                        # ロスカットチェック
                        self._strategy.loss_cut_check()

                        # 売買判断
                        self._strategy.logic()

            if side_values[i] == 'BUY':
                self.buy_size_total += size_values[i]
                self._best_ask = self._ltp
            else:
                self.sell_size_total += size_values[i]
                self._best_bid = self._ltp

            # self._order最終値からさかのぼって注文を確認
            startpoint = self._order_start_position
            self._order_start_position = len(self._order)
            for j in range(startpoint, len(self._order)):
                # orderitemにはself._order[j]への参照がはいるだけなので、orderitemへの変更処理はself._order[j]への変更処理になる
                orderitem = self._order[j]

                if orderitem['status'] == 'ACTIVE':  # 注文が約定も期限切れもしていない場合
                    # 最初に見つけたACTIVEなオーダーを次のスタートポイントにする
                    self._order_start_position = min(
                        self._order_start_position, j)
                    order_timestamp = orderitem['timestamp']
                    time_diff = self.now_time - order_timestamp

                    # 発注時刻からMTE(分)だけ経過していれば注文を無効化
                    if time_diff > self.strategy_config['minutes_to_expire']*60+self.busy_rate*self._delay or time_diff < 0:
                        orderitem['status'] = 'EXPIRED'
                        orderitem['completed_date'] = self._exec_date

                    # Buy注文が約定した場合 (エントリーからDELAY秒までは約定させない)
                    if orderitem['side'] == 'BUY' and self._ltp < orderitem['price'] and time_diff >= self.busy_rate*self._delay:
                        if orderitem['price'] == market_buy:  # 成買いの場合にはLTP価格で決済
                            orderitem['price'] = self._ltp + \
                                self._config['slipage']
                        if self.now_time == order_timestamp:  # 最新のオーダーの場合（成買いに相当）
                            orderitem['price'] = self._ltp + \
                                self._config['slipage']
                        self._pos += orderitem['size']  # ポジションを増やす
                        exec_price -= orderitem['price'] * \
                            orderitem['size']  # 取得価格の更新
                        orderitem['status'] = 'COMPLETED'  # ポジションを増やす
                        orderitem['completed_date'] = self._exec_date
                        hit += 1

                    # Sell注文が約定した場合 (エントリーからDELAY秒までは約定させない)
                    elif orderitem['side'] == 'SELL' and self._ltp > orderitem['price'] and time_diff >= self.busy_rate*self._delay:
                        if orderitem['price'] == market_sell:  # 成売りの場合にはLTP価格で決済
                            orderitem['price'] = self._ltp - \
                                self._config['slipage']
                        if self.now_time == order_timestamp:  # 最新のオーダーの場合（成買いに相当）
                            orderitem['price'] = self._ltp - \
                                self._config['slipage']
                        self._pos -= orderitem['size']  # ポジションを減らす
                        exec_price += orderitem['price'] * \
                            orderitem['size']  # 取得価格の更新
                        orderitem['status'] = 'COMPLETED'
                        orderitem['completed_date'] = self._exec_date
                        hit += 1

            self.pnl_values[i] = exec_price + self._pos * \
                self._ltp  # 損益を計算し、Numpy Ndarrayに保存
            pos_values[i] = self._pos  # ポジションをNumpy Ndarrayに保存

            previous_second = self.now_second

        if not multicore:
            dft.pos = pos_values  # ポジションをNumpy NdarrayからPandas Seriesへ変換
            dft.pnl = self.pnl_values  # 損益をNumpy NdarrayからPandas Seriesへ変換
        dft['profitMax'] = dft['pnl'].rolling(
            window=5000000, min_periods=0).max().replace(np.nan, 0)  # 損益の最大値
        dft['DD'] = dft['pnl'] - dft['profitMax']  # ドローダウン
        mdd = int(dft['DD'].min())  # 最大ドローダウン
        maxpos = round(dft.pos.max(), 2)  # 最大Buyポジション
        minpos = round(dft.pos.min(), 2)  # 最大Sellポジション

        param_str = ''
        for key, value in self.strategy_config['parameters'].items():
            if type(value) is float:
                value = round(value, 8)
            if type(value) is np.float64:
                value = round(value, 8)
            param_str += '{} {} /'.format(key, value)
        result_str = 'PnL:{} /MDD:{} /MaxPos:{:.2f} /MinPos:{:.2f} /order:{} /hit:{}'.format(
            int(dft.pnl.values[-1]), mdd, maxpos, minpos, len(self._order), hit)
        config_str = 'MTE:{} /SEC:{} /DELAY:{}'.format(
            self.strategy_config['minutes_to_expire'], self.strategy_config['timescale'], self._delay)
        self._logger.info("{} /{}{}".format(config_str, param_str, result_str))
        self._logger.info("{:.3f}sec".format(time.time() - starttime))

        if multicore:
            return pos_values, self.pnl_values, param_str[:-2], round(int(self.pnl_values[-1])/max(abs(maxpos), abs(minpos)))
        else:
            return dft, param_str[:-2], round(int(self.pnl_values[-1])/max(abs(maxpos), abs(minpos)))

    # Strategyクラスから呼び出される
    @property
    def _is_backtesting(self):
        return True

    @property
    def _average(self):
        return self._ltp

    @property
    def _profit(self):
        return self.pnl_values[-1]

    @property
    def _profit_unreal(self):
        return 0

    @property
    def _server_latency(self):
        return self.busy_rate*self._delay*500

    @property
    def _server_latency_rate(self):
        return self.busy_rate*self._delay*500

    @property
    def _server_health(self):
        return 'NORMAL'

    @property
    def _current_candle(self):
        return {'open': self.temp_open, 'high': self.temp_high, 'low': self.temp_low, 'close': self._ltp, 'volume': self.buy_size_total+self.sell_size_total, 'buy': self.buy_size_total, 'sell': self.sell_size_total}

    @property
    def _from_lastcandle_update(self):
        return self.elapsed_time_from_candle % self.strategy_config['timescale']

    @property
    def _api_count(self):
        return sum(self.api_counter)

    def _limit_buy(self, price, size, time_in_force):
        self.api_counter[-1] += 1
        id = 'JRF' + str(self._id_count)
        self._id_count += 1
        self._order.append({'timestamp': self.now_time, 'exec_date': self._exec_date, 'side': 'BUY',
                            'price': price, 'size': size, 'status': 'ACTIVE', 'completed_date': '', 'id': id})
        return {'child_order_acceptance_id': id}

    def _limit_sell(self, price, size, time_in_force):
        self.api_counter[-1] += 1
        id = 'JRF' + str(self._id_count)
        self._id_count += 1
        self._order.append({'timestamp': self.now_time, 'exec_date': self._exec_date, 'side': 'SELL',
                            'price': price, 'size': size, 'status': 'ACTIVE', 'completed_date': '', 'id': id})
        return {'child_order_acceptance_id': id}

    def _market_buy(self, size, nocheck=False):
        self.api_counter[-1] += 1
        id = 'JRF' + str(self._id_count)
        self._id_count += 1
        self._order.append({'timestamp': self.now_time, 'exec_date': self._exec_date, 'side': 'BUY',
                            'price': market_buy, 'size': size, 'status': 'ACTIVE', 'completed_date': '', 'id': id})
        return True

    def _market_sell(self, size, nocheck=False):
        self.api_counter[-1] += 1
        id = 'JRF' + str(self._id_count)
        self._id_count += 1
        self._order.append({'timestamp': self.now_time, 'exec_date': self._exec_date, 'side': 'SELL',
                            'price': market_sell, 'size': size, 'status': 'ACTIVE', 'completed_date': '', 'id': id})
        return True

    def _close_position(self):
        self._pending_time = self.now_time + \
            self.strategy_config['emergency_wait']
        if self._pos > 0:
            return self._market_sell(self._pos)
        elif self._pos < 0:
            return self._market_buy(-self._pos)

    def logic(self):
        return

    def _cancel_all_orders(self):
        startpoint = self._order_start_position
        for j in range(startpoint, len(self._order)):
            # orderitemにはself._order[j]への参照がはいるだけなので、orderitemへの変更処理はself._order[j]への変更処理になる
            orderitem = self._order[j]
            order_timestamp = orderitem['timestamp']
            time_diff = self.now_time - order_timestamp
            # 注文が約定も期限切れもしていない場合 (delay期間以内のキャンセルは間に合わない）
            if orderitem['status'] == 'ACTIVE'and time_diff >= self.busy_rate*self._delay:
                orderitem['status'] = 'EXPIRED'
            break

    def _cancel_childorder(self, id):
        startpoint = self._order_start_position
        for j in range(startpoint, len(self._order)):
            # orderitemにはself._order[j]への参照がはいるだけなので、orderitemへの変更処理はself._order[j]への変更処理になる
            orderitem = self._order[j]
            if (orderitem['id'] == id):
                order_timestamp = orderitem['timestamp']
                time_diff = self.now_time - order_timestamp
                # 注文が約定も期限切れもしていない場合 (delay期間以内のキャンセルは間に合わない）
                if orderitem['status'] == 'ACTIVE'and time_diff >= self.busy_rate*self._delay:
                    orderitem['status'] = 'EXPIRED'
                break

    @property
    def _minimum_order_size(self):
        return 0.01


if __name__ == '__main__':

    # loggerの準備
    logger = setup_logger()

    # configファイル読み込み
    config = yaml.safe_load(
        open('backtest_scalpingmode.yaml', 'r', encoding='utf-8_sig'))

    # 引数の処理
    if len(sys.argv) == 3:
        config['strategy_py'] = sys.argv[1]
        config['strategy_yaml'] = sys.argv[2]

    # 約定履歴の読み込み
    df = load_cvs_files(logger, config)

    # バックテスト初期化
    backtest = backtest(logger, config)

    backtest_done = False
    if 'optimize' in config and config['optimize'] != None:
        for key, value in config['optimize'].items():
            if key not in backtest.strategy_config['parameters'] and key != 'minutes_to_expire':
                print("{} is not in parameters".format(key))
            else:
                original = backtest.strategy_config['parameters'][key]
                x = np.arange(value[0], value[1], value[2])
                print("key:{} = {}".format(key, x))
                result = []
                for i in x:
                    backtest.strategy_config['parameters'][key] = i

                    # バックテスト実施
                    dft, title, profit = backtest.run(df)
                    # グラフのプロット
                    plot_graph(dft, config['fix_timescale'], title=title, filename=title.replace(
                        '/', '').replace(':', '')+'.png')

                    backtest_done = True
                    result.append(profit)

                result_df = pd.DataFrame({"profit": result}, index=x)
                result_df.plot()
                plt.xlabel(key, fontsize=10)
                plt.ylabel("profit", fontsize=10)
                plt.savefig("{}.png".format(key))
                backtest.strategy_config['parameters'][key] = original

    if not backtest_done:
        # バックテスト実施
        dft, title, profit = backtest.run(df)
        # グラフのプロット
        plot_graph(dft, config['fix_timescale'],
                   title=title, filename=config['output_files'])
