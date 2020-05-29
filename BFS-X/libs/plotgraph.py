# -*- coding: utf-8 -*-
from libs import plotgraph_proc
import pandas
import os
import csv
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timedelta
from threading import Thread
from copy import deepcopy
from statistics import median
import requests


def median2(q):
    return median(q) if len(q) != 0 else 0


epsilon = 1e-7


def mean(q):
    return sum(q) / (len(q) + epsilon)


# ポジショングラフを描画するクラス


class PositionGraph:

    _pos_history = deque(maxlen=240)  # 1分毎、4H分のポジション履歴
    _minutes_counter = 61
    _seconds_counter = 0

    _initial_collateral = 0
    _fixed_pnl = 0
    _open_pnl = 0
    _today = '00'
    _last_profit = 0

    _profit_history = deque(maxlen=1440)  # 1分毎、24H分の損益履歴
    _profit_all_history = deque(maxlen=2400)  # 1時間毎、100日分の損益履歴

    def __init__(self, logger, api, parameters):
        self._logger = logger
        self._api = api
        self._parameters = parameters
        self._today = (datetime.utcnow()+timedelta(hours=9)).strftime("%d")
        self._day_changed = False
        self._day_changed_pnl = 0
        self._restore_profit_history()
        self._pnl_until_yesterday = 0
        self._restore_profit_all_history()

        # グラフのプロットを別スレッドで起動するクラス
        self._protgraph_thread = plotgraph_proc.PositionGraphThread(
            self._logger)

    # 停止・再起動しても本日の損益グラフを保持するための情報保管ファイル

    def __profit_csvfilename(self):
        return self._parameters._strategy['log_folder']+"profit.csv"

    def _profit_history_append(self, ltp):
        currenttime = (datetime.utcnow()+timedelta(hours=9)).timestamp()
        self._profit_history.append([
            currenttime,
            ltp,
            # apiから取得した証拠金推移から計算した利益（確定済み利益)
            self._fixed_pnl-self._initial_collateral,
            self._open_pnl,                               # apiから取得した証拠金推移から計算した利益（含み利益)
            self._parameters._strategy_class.current_profit - \
            self._parameters.estimated_profit_unrealized,
                                                          # 約定履歴から自炊した利益（確定済み利益のみ)
            self._parameters.estimated_profit_unrealized,  # 約定履歴から自炊した含み損益
            self._parameters._strategy_class.current_pos,  # 想定ポジション
            (datetime.utcnow()+timedelta(hours=9)).strftime('%H:%M:%S'),
            self._parameters.sfd_commission
        ])
        with open(self.__profit_csvfilename(), 'a') as profithistoryfile:
            profithistorycsv = csv.writer(
                profithistoryfile, lineterminator='\n')
            profithistorycsv.writerow(self._profit_history[-1])

    def _restore_profit_history(self):
        self._profit_history.clear()
        if os.path.exists(self.__profit_csvfilename()):
            try:
                with open(self.__profit_csvfilename(), 'r') as profithistoryfile:
                    profithistorycsv = csv.reader(profithistoryfile)
                    today = (datetime.utcnow()+timedelta(hours=9)).day
                    for p in profithistorycsv:
                        if len(p) < 9:
                            p.append(0)
                        if datetime.fromtimestamp(float(p[0])).day == today:
                            self._profit_history.append([float(p[0]), int(float(p[1])), int(float(p[2])), int(
                                float(p[3])), int(float(p[4])), int(float(p[5])), round(float(p[6]), 8), "", int(float(p[8]))])
                            self._parameters.sfd_commission = int(float(p[8]))
                        else:
                            self._day_changed = True
                            self._day_changed_pnl = int(
                                float(p[4])) + int(float(p[5]))

            except Exception as e:
                self._logger.exception("Error while restoreing profit history : {}, {}".format(
                    e, traceback.print_exc()))

    # 長期の損益を表示するための情報保管ファイル
    def __profit_all_csvfilename(self):
        return self._parameters._strategy['log_folder']+"profit_all.csv"

    def _profit_all_history_append(self, ltp):
        currenttime = (datetime.utcnow()+timedelta(hours=9)).timestamp()
        self._profit_all_history.append([
            currenttime,
            ltp,
            self._pnl_until_yesterday + self._parameters._strategy_class.current_profit,  # トータル損益
            self._parameters._strategy_class.current_profit -
            self._parameters.estimated_profit_unrealized,
            # 約定履歴から自炊した利益（確定済み利益のみ)
            self._parameters._strategy_class.current_profit,  # 約定履歴から自炊した利益（含み損益も含む）
            self._pnl_until_yesterday,                        # 前日までの確定損益
            (datetime.utcnow()+timedelta(hours=9)).strftime('%H:%M:%S'),
            self._parameters.sfd_commission
        ])
        with open(self.__profit_all_csvfilename(), 'a') as profithistoryfile:
            profithistorycsv = csv.writer(
                profithistoryfile, lineterminator='\n')
            profithistorycsv.writerow(self._profit_all_history[-1])

    def _restore_profit_all_history(self):
        self._profit_all_history.clear()
        if os.path.exists(self.__profit_all_csvfilename()):
            try:
                with open(self.__profit_all_csvfilename(), 'r') as profithistoryfile:
                    profithistorycsv = csv.reader(profithistoryfile)
                    for p in profithistorycsv:
                        if len(p) < 8:
                            p.append(0)
                        #                                  timestamp    ltp
                        self._profit_all_history.append([float(p[0]), int(float(p[1])), int(
                            # total_profit      fixed_pn  l     pnl          pnl_until_yesterday
                            float(p[2])), int(float(p[3])), int(float(p[4])), int(float(p[5])), int(float(p[7]))])
                        self._pnl_until_yesterday = int(float(p[5]))

                if self._day_changed == True:
                    self._pnl_until_yesterday += self._day_changed_pnl
                    os.remove(self.__profit_csvfilename())
                    self._last_profit = 0
                    self._parameters._strategy_class.reset_profit()
                    self._parameters.executed_size_today = 0              # 取引高
                    self._profit_all_history_append(
                        list(self._profit_all_history)[-1][1])
                    self.__plot_plofit_graph_bfcolor(list(self._profit_all_history), average=1,
                                                     fmt='%m/%d %H:%M', rotate=45, discord_webhook='profit_discord_webhooks')

            except Exception as e:
                self._logger.exception("Error while restoreing profit history : {}, {}".format(
                    e, traceback.print_exc()))

    # レイテンシ履歴の最小値　（このサーバーでの平均的な速度）
    def _getLatencyMin(self):
        return min(list(self._parameters.latency_history))

    # レイテンシの直近10秒の最大値
    def _getLatencyMax(self):
        return max(list(self._parameters.latency_history)[-10:])

    # 直近の遅延
    def getLatencyRate(self):
        return int(self._getLatencyMax()-self._getLatencyMin())

    def notify_position_change(self, ltp):
        """
        ポジション変化をグラフ通知する
        :return:
        """

        # レイテンシを 1 秒毎に記録して保存
        current_second = int(time.time()) % 60
        if self._seconds_counter != current_second:
            self._seconds_counter = current_second
            self._parameters.server_latency_history.append(
                [datetime.utcnow()+timedelta(hours=9), self._parameters.latency_history[-1], ltp])

        # ポジション履歴を 1 分毎に記録して保存
        current_minutes = int(time.time() / 60) % 60
        if self._minutes_counter != current_minutes:

            self._parameters.ordered_count.append(0)               # 出した指値の数
            self._parameters.order_filled_count.append(0)         # 完全約定された数
            self._parameters.order_not_filled_count.append(0)     # 全く約定しなかった数
            self._parameters.order_partial_filled_count.append(0)  # 部分的に約定した数
            self._parameters.order_taked.append(0)                # 成り行きで約定した数
            self._parameters.order_retry_count.append(0)          # オーダーリトライの回数
            self._parameters.executed_size.append(0)              # 取引高

            pos_qty = self._parameters.estimated_position
            pos_price = self._parameters.counted_average_price

            self._parameters.estimated_profit_unrealized = round(
                (ltp-self._parameters.counted_average_price)*self._parameters.counted_position)

            # 初回と日付が変わった最初にはapiで証拠金を取得
            if self._parameters._strategy_class.sim_mode == False and self._initial_collateral == 0:
                try:
                    collateral = self._api.getcollateral()
                    self._logger.debug('(getcollateral) PrivateAPI  LimitPeriod:{} LimitRemaining:{}'.format(
                        self._api.LimitPeriod, self._api.LimitRemaining))
                    self._fixed_pnl = int(collateral["collateral"])
                    self._open_pnl = int(collateral["open_position_pnl"])
                    self._parameters.collateral_profit_unrealized = self._open_pnl
                    print(collateral)
                except:
                    pass
                self._current_collateral = self._fixed_pnl + self._open_pnl
                self._initial_collateral = self._current_collateral - \
                    self._parameters.estimated_profit - self._parameters.estimated_profit_unrealized

            window = 5  # 5分の平均を算出
            self._pos_history.append([
                (datetime.utcnow()+timedelta(hours=9)).timestamp(),
                ltp,
                self._parameters._strategy_class.current_pos,
                pos_price,
                abs(self._parameters._strategy_class.current_pos),
                self.getLatencyRate(),
                self._parameters.superbusy_happend,
                # 約定履歴から自炊した損益
                self._parameters._strategy_class.current_profit + self._parameters.sfd_commission,
                # 直近５分のAPIアクセス回数 [8]
                self._parameters._strategy_class.api_count,
                # 出した指値の数            [9]
                self._parameters.ordered_count[-2],
                sum(list(self._parameters.order_filled_count)
                    [-min(len(self._parameters.order_filled_count), window+1):-1]),  # 完全約定された数          [10]
                # 完全約定率                [11]
                sum(self._parameters.order_filled_count) / \
                (sum(self._parameters.ordered_count)+epsilon)*100,
                # 成行約定数                [12]
                sum(list(self._parameters.order_taked)
                    [-min(len(self._parameters.order_taked), window+1):-1]),
                # 成行指値率                [13]
                sum(self._parameters.order_taked) / \
                (sum(self._parameters.order_filled_count)+epsilon)*100,
                # 直近５分のAPIアクセス回数 [14]
                self._parameters._strategy_class.api_order_count
            ])
            self._parameters.superbusy_happend = False

            self._profit_history_append(ltp)

            # 一定期間ごとにプロット(別スレッドにて)
            thread = threading.Thread(target=self.__plot_graphs, args=())
            thread.start()

            # 1時間に1回
            if self._minutes_counter > current_minutes:
                self._profit_all_history_append(ltp)

        self._minutes_counter = current_minutes

    def __plot_graphs(self):
        self._logger.info('          api counter : order {}  getorder {} cancel {}'.format(len(
            self._parameters.api_sendorder_speed), len(self._parameters.api_getorder_speed), len(self._parameters.api_cancel_speed)))
        self._logger.info('          api speed   : order {:.0f}msec  getorder {:.0f}msec cancel {:.0f}msec'.format(median2(list(
            self._parameters.api_sendorder_speed)), median2(list(self._parameters.api_getorder_speed)), median2(list(self._parameters.api_cancel_speed))))

        current_minutes = int(time.time() / 60)
        # 一定期間ごとにプロット
        if self._parameters._strategy['position_interval'] != 0 and current_minutes % self._parameters._strategy['position_interval'] == 0 and len(self._pos_history) > 2:
            self.__plot_position_graph(list(self._pos_history))

        # 一定期間ごとにプロット (profit_intervalが0ならば日付が変わったときだけ1回）
        if(((self._parameters._strategy['profit_interval'] == 0 and self._today != (datetime.utcnow()+timedelta(hours=9)).strftime("%d")) or
                (self._parameters._strategy['profit_interval'] != 0 and current_minutes % self._parameters._strategy['profit_interval'] == 0)) and len(self._profit_history) > 2):
            if 'bitflyer_color' in self._parameters._strategy and self._parameters._strategy['bitflyer_color']:
                self.__plot_plofit_graph_bfcolor(list(self._profit_history))
            else:
                self.__plot_plofit_graph(list(self._profit_history))

        if self._today != (datetime.utcnow()+timedelta(hours=9)).strftime("%d"):
            self.first_time = True

        if current_minutes % 60 == 0:  # 1時間ごとに現在のステータスをログに
            log_text = '---------------------Order counts'
            self._logger.info(log_text)
            message = log_text

            log_text = '    ordered         : {}'.format(
                sum(self._parameters.ordered_count))               # 出した指値の数
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = '    order filled   : {}'.format(
                sum(self._parameters.order_filled_count))         # 完全約定された数
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = '    orde taked     : {}'.format(
                sum(self._parameters.order_taked))                # 成り行きで約定した数
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = '    partial filled : {}'.format(
                sum(self._parameters.order_partial_filled_count))  # 部分的に約定した数
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = '    order cancelled: {}'.format(
                sum(self._parameters.order_not_filled_count))     # 全く約定しなかった数
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = '    api : order {}  getorder {} cancel {}'.format(len(self._parameters.api_sendorder_speed), len(
                self._parameters.api_getorder_speed), len(self._parameters.api_cancel_speed))
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = '    retry counter  : {}'.format(
                sum(self._parameters.order_retry_count))               # リトライの回数
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = ''
            self._logger.info(log_text)
            message += '\n' + log_text

            if sum(self._parameters.ordered_count) > 0:
                log_text = '    filled rate         : {:.1f}%'.format(sum(
                    self._parameters.order_filled_count)/(sum(self._parameters.ordered_count)+epsilon)*100)
                self._logger.info(log_text)
                message += '\n' + log_text

                log_text = '    order taked rate    : {:.1f}%'.format(sum(
                    self._parameters.order_taked)/(sum(self._parameters.order_filled_count)+epsilon)*100)
                self._logger.info(log_text)
                message += '\n' + log_text

            if sum(self._parameters.order_filled_count)+sum(self._parameters.order_partial_filled_count) > 0:
                log_text = '    partial filled rate : {:.1f}%'.format(sum(self._parameters.order_partial_filled_count)/(
                    sum(self._parameters.order_filled_count)+sum(self._parameters.order_partial_filled_count)+epsilon)*100)
                self._logger.info(log_text)
                message += '\n' + log_text

            if self._parameters.sfd_commission != 0:
                log_text = '    SFD factor          : {:.1f}'.format(
                    -self._parameters.sfd_profit/self._parameters.sfd_loss if self._parameters.sfd_loss != 0 else 0)
                self._logger.info(log_text)
                message += '\n' + log_text

            log_text = '    api counter         : {:.1f}times/min'.format((len(self._parameters.api_sendorder_speed)+len(
                self._parameters.api_getorder_speed)+len(self._parameters.api_cancel_speed))/60)
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = ''
            self._logger.info(log_text)
            message += '\n' + log_text

            profit = self._parameters._strategy_class.current_profit
            log_text = '    executed volume /h  : {:.2f}BTC  (JPY{:+,.0f}/BTC)'.format(sum(self._parameters.executed_size), ((
                profit-self._last_profit)/sum(self._parameters.executed_size)*2 if sum(self._parameters.executed_size) != 0 else 0))         # 取引高
            self._logger.info(log_text)
            message += '\n' + log_text
            self._last_profit = profit

            log_text = '    exec volume today   : {:.2f}BTC  (JPY{:+,.0f}/BTC)'.format(self._parameters.executed_size_today, (
                profit/self._parameters.executed_size_today*2 if self._parameters.executed_size_today != 0 else 0))        # 当日取引高
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = ''
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = 'Current Parameter [parameters] : {}'.format(
                self._parameters._strategy['parameters'])
            self._logger.info(log_text)
            message += '\n' + log_text

            log_text = ''
            self._logger.info(log_text)
            message += '\n' + log_text

            if self._parameters._strategy['position_interval'] != 0:
                try:
                    if self._parameters._strategy['position_discord_webhooks'] != '':
                        payload = {'content': ' {} '.format(message)}
                        requests.post(self._parameters._strategy['position_discord_webhooks'],
                                      data=payload, timeout=10)

                except Exception as e:
                    self._logger.error(
                        'Failed sending image to Discord: {}'.format(e))

                # 約定率グラフ
                self.__plot_rate_graph(list(self._pos_history))

                # サーバーレスポンスヒストグラム
                self.__plot_histgram(list(self._parameters.api_sendorder_speed), list(
                    self._parameters.api_getorder_speed), list(self._parameters.api_cancel_speed))

            self._parameters.api_sendorder_speed.clear()
            self._parameters.api_getorder_speed.clear()
            self._parameters.api_cancel_speed.clear()

            # サーバー処理時間グラフ
            if self._parameters._strategy['position_interval'] != 0:
                self.__plot_latency()
            self._parameters.server_order_delay_history.clear()
            self._parameters.server_cancel_delay_history.clear()
            self._parameters.server_latency_history.clear()
            self._parameters.all_latency_history.clear()

        # 日付が変わったら損益をリセット
        if self._today != (datetime.utcnow()+timedelta(hours=9)).strftime("%d"):
            self._today = (datetime.utcnow()+timedelta(hours=9)).strftime("%d")
            # 前日までの損益に当日の利益を加算
            self._pnl_until_yesterday += self._parameters._strategy_class.current_profit
            self._profit_history.clear()
            os.remove(self.__profit_csvfilename())
            self._pos_history.clear()
            self._initial_collateral = 0
            self._last_profit = 0
            self._parameters._strategy_class.reset_profit()
            self._parameters.executed_size_today = 0              # 取引高
            self._parameters.sfd_commission = 0
            self._parameters.sfd_profit = 0
            self._parameters.sfd_loss = 0
            self._profit_all_history_append(
                list(self._profit_all_history)[-1][1])
            self.__plot_plofit_graph_bfcolor(list(self._profit_all_history), average=1,
                                             fmt='%m/%d %H:%M', rotate=45, discord_webhook='profit_discord_webhooks')

    def __plot_position_graph(self, position_history):

        self._logger.info('Start drawing position graph')

        history_time = [datetime.fromtimestamp(
            s[0]) for s in position_history]            # 時刻
        # BTC価格
        price = [p[1] for p in position_history]
        average = [p[3] if p[3] != 0 else p[1]
                   for p in position_history]                  # 平均建玉価格
        # 保有ポジション（絶対値）
        leverage = [p[4] for p in position_history]
        # 保有ポジション　プラス＝ロング、マイナス＝ショート
        position = [p[4] if p[2] > 0 else -p[4] for p in position_history]
        normal = [10000000 if p[5] < self._parameters._strategy['display_normal']
                  else 0 for p in position_history]
        very_busy = [10000000 if p[5] > self._parameters._strategy['display_busy']
                     else 0 for p in position_history]
        super_busy = [10000000 if p[6] else 0 for p in position_history]
        # 損益
        profit = [p[7] for p in position_history]
        # apiカウント
        api_count = [p[8] for p in position_history]
        api_order = [int(p[14]*500/300)
                     for p in position_history]               # apiカウント

        Thread(target=self._protgraph_thread.plot_position_graph_thread,
               args=(history_time, price, average,
                     leverage, position,
                     normal, very_busy, super_busy,
                     profit, api_count, api_order,
                     self._parameters._strategy['log_folder']+'position.png',
                     self._parameters.strategy_config_file,
                     self._parameters._strategy['position_discord_webhooks'],
                     self._parameters._strategy['plot_delay'] if 'plot_delay' in self._parameters._strategy else 0
                     )).start()

    def __plot_plofit_graph_bfcolor(self, profit_history, average=20, fmt='%H:%M', rotate=0, discord_webhook='profit_discord_webhooks'):

        self._logger.debug('Start drawing profit graph')

        start_pnl_values = profit_history[0][4]+profit_history[0][5]

        history_timestamp = [s[0] for s in profit_history]
        price_history_raw = [s[4]+s[5] -
                             start_pnl_values for s in profit_history]
        price_history = list(pandas.Series(price_history_raw).rolling(
            window=average, min_periods=1).mean())
        price_history[-1] = price_history_raw[-1]

        Thread(target=self._protgraph_thread.plot_plofit_graph_bfcolor_thread,
               args=(history_timestamp, price_history, average, fmt, rotate,
                     self._parameters._strategy['log_folder']+'profit.png',
                     self._parameters._strategy[discord_webhook],
                     self._parameters._strategy['plot_delay'] if 'plot_delay' in self._parameters._strategy else 0
                     )).start()

    def __plot_plofit_graph(self, profit_history):

        self._logger.info('Start drawing profit graph')

        start_fixed_pnl_values = profit_history[0][4]
        start_pnl_values = profit_history[0][4]+profit_history[0][5]

        history_time = [datetime.fromtimestamp(
            s[0]) for s in profit_history]            # 時刻

        price_values = [s[1] for s in profit_history]
        fixed_pnl_values = [
            s[4]-start_fixed_pnl_values for s in profit_history]
        pnl_values = [s[4]+s[5]-start_pnl_values for s in profit_history]
        pos_values = [s[6] for s in profit_history]
        sfd_values = [s[8] for s in profit_history]

        Thread(target=self._protgraph_thread.plot_plofit_graph_thread,
               args=(history_time, price_values, fixed_pnl_values, pnl_values, pos_values, sfd_values,
                     self._parameters._strategy['disp_position'], self._parameters._strategy['disp_realized_profit'],
                     self._parameters._strategy['log_folder'] +
                     'profit.png', self._parameters._strategy['profit_discord_webhooks'],
                     self._parameters._strategy['plot_delay'] if 'plot_delay' in self._parameters._strategy else 0
                     )).start()

    def __plot_rate_graph(self, position_history):
        if 'plot_execute_rate' in self._parameters._strategy and self._parameters._strategy['plot_execute_rate']==False :
            return

        self._logger.info('Start drawing filled rate graph')

        if len(position_history) == 0:
            return

        history_time = [datetime.fromtimestamp(
            s[0]) for s in position_history]    # 時刻
        profit_estimated = [p[7]
                            for p in position_history]                       # 損益
        ordered_count = [p[9]
                         for p in position_history]                           # オーダー数
        filled_count = [p[10]
                        for p in position_history]                          # 完全約定数
        order_filled_rate = [p[11]
                             for p in position_history]                     # 完全約定率
        taked_count = [p[12]
                       for p in position_history]                           # 成行約定数
        order_taked_rate = [p[13]
                            for p in position_history]                      # 成行指値率

        # 現在時刻よりも4時間以前を削除
        while len(self._parameters.slipage_history) != 0:
            s = self._parameters.slipage_history.popleft()
            if s[0] < datetime.utcnow()+timedelta(hours=9)-timedelta(hours=4):
                continue
            self._parameters.slipage_history.appendleft(s)
            break
        slipage_history = list(self._parameters.slipage_history)

        Thread(target=self._protgraph_thread.plot_rate_graph_thread,
               args=(history_time, profit_estimated, ordered_count, filled_count,
                     order_filled_rate, taked_count, order_taked_rate, slipage_history,
                     self._parameters._strategy['log_folder'] +
                     'order_rate.png',
                     self._parameters._strategy['position_discord_webhooks'],
                     self._parameters._strategy['plot_delay'] if 'plot_delay' in self._parameters._strategy else 0
                     )).start()

    # サーバーレスポンスとレイテンシとヒストグラム描画

    def __plot_histgram(self, list1, list2, list3):

        if 'plot_api_speed' in self._parameters._strategy and self._parameters._strategy['plot_api_speed']==False :
            return

        if len(list1)+len(list2)+len(list3) == 0:
            return

        self._logger.info('Start drawing api speed histogram')

        Thread(target=self._protgraph_thread.plot_histgram_thread,
               args=(deepcopy(list1), deepcopy(list2), deepcopy(list3),
                     self._parameters._strategy['log_folder']+'api_speed.png',
                     self._parameters._strategy['position_discord_webhooks'],
                     self._parameters._strategy['plot_delay'] if 'plot_delay' in self._parameters._strategy else 0
                     )).start()

    # サーバーレスポンスとレイテンシとヒストグラム描画

    def __plot_latency(self):
        if 'plot_order_event' in self._parameters._strategy and self._parameters._strategy['plot_order_event']==False :
            return

        if len(self._parameters.server_order_delay_history)+len(self._parameters.server_cancel_delay_history)+len(self._parameters.server_latency_history) == 0:
            return

        self._logger.info('Start drawing server speed graph')

        Thread(target=self._protgraph_thread.plot_latency_thread,
               args=(deepcopy(self._parameters.server_order_delay_history),
                     deepcopy(self._parameters.server_cancel_delay_history),
                     deepcopy(self._parameters.server_latency_history),
                     mean(self._parameters.all_latency_history),
                     self._parameters._strategy['log_folder'] +
                     'server_speed.png',
                     self._parameters._strategy['position_discord_webhooks'],
                     self._parameters._strategy['plot_delay'] if 'plot_delay' in self._parameters._strategy else 0
                     )).start()
