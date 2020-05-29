# coding: utf-8
import sys
import pandas
import requests
import traceback
import matplotlib
matplotlib.use('Agg')
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pybitflyer
from libs import parameters
from libs import candlegen
from libs import bforder
from logging import getLogger, INFO, DEBUG, StreamHandler, FileHandler, Formatter
from threading import Thread, Lock
import time
import os
import zipfile
import signal
import socket
import websocket
import json
from datetime import datetime, timedelta
from datetime import time as datetime_time
from collections import deque
# from pandas.plotting import register_matplotlib_converters
# register_matplotlib_converters()
pandas.plotting.register_matplotlib_converters()

# Influx DBとの接続
try:
    from influxdb import InfluxDBClient
except:
    pass

# ロガーの作成


def setup_logger():
    logger = getLogger(__name__)
    logger.setLevel(DEBUG)
    handler = StreamHandler()
    handler.setFormatter(Formatter(
        fmt='%(asctime)s.%(msecs)03d:  %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    handler.setLevel(INFO)
    logger.addHandler(handler)
    return logger


last_day = '00'
log_filename = ''


def update_filehandler(logger):
    global last_day
    global log_filename
    day = time.strftime("%d")
    if last_day != day:   # 日付が変わったら出力ファイルを変更
        for h in logger.handlers[0:]:
            logger.removeHandler(h)     # logger.handlersを除去

        handler = StreamHandler()
        handler.setFormatter(Formatter(
            fmt='%(asctime)s.%(msecs)03d:  %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        handler.setLevel(INFO)
        logger.addHandler(handler)

        previous_filename = log_filename
        log_filename = 'position_server' + time.strftime('%Y-%m-%d')
        fh = FileHandler(log_filename + '.log')
        fh.setFormatter(Formatter(
            fmt='%(asctime)s.%(msecs)03d[%(levelname)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        fh.setLevel(DEBUG)
        logger.addHandler(fh)           # 日ごとのファイルハンドラを追加
        last_day = day

        # ログの圧縮を別スレッドで起動
        if previous_filename != '':
            thread_z = Thread(target=ziplog, args=(previous_filename,))
            thread_z.start()

# ログの圧縮して削除


def ziplog(previous_filename):
    with zipfile.ZipFile(previous_filename + '.zip', 'w') as log_zip:
        log_zip.write(previous_filename + '.log', arcname=previous_filename +
                      '.log', compress_type=zipfile.ZIP_DEFLATED)
    os.remove(previous_filename + '.log')


# 現物価格をwebsocketで取得
class WebsocketTicks(object):
    def __init__(self, parent):
        self._parent = parent
        self.startWebsocket()

    def startWebsocket(self):
        def on_open(ws):
            print("Websocket connected")
            ws.send(json.dumps({"method": "subscribe", "params": {
                    "channel": "lightning_ticker_BTC_JPY"}}))
            ws.send(json.dumps({"method": "subscribe", "params": {
                    "channel": "lightning_ticker_FX_BTC_JPY"}}))

        def on_error(ws, error):
            print(error)

        def on_close(ws):
            print("Websocket closed")

        def run(ws):
            while True:
                ws.run_forever()
                time.sleep(1)

        def on_message(ws, message):
            try:
                messages = json.loads(message)
                params = messages["params"]
                channel = params["channel"]
                if channel == "lightning_ticker_BTC_JPY":
                    self._parent.spot_price = int(params["message"]["ltp"])
                elif channel == "lightning_ticker_FX_BTC_JPY":
                    self._parent.fx_price = int(
                        messages["params"]["message"]["ltp"])
                else:
                    print(channel)
            except:
                print("Erro websocket: {}".format(message))
        ws = websocket.WebSocketApp("wss://ws.lightstream.bitflyer.com/json-rpc",
                                    on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
        websocketThread = Thread(target=run, args=(ws, ))
        websocketThread.start()


MAX_MESSAGE = 2048


class position_server:
    def __init__(self):
        # ロガーの初期化
        self._logger = setup_logger()
        update_filehandler(self._logger)

        # パラメータ管理クラス
        self._parameters = parameters.Parameters(self._logger)

        if len(sys.argv) == 1:
            # configファイル読み込み
            self._parameters.load_config_file('trade.yaml')

        else:
            # configファイル読み込み
            self._parameters.load_config_file(sys.argv[1])

        if self._parameters._config['apikey'] != '' and self._parameters._config['secret'] != '':
            # 売買用クラス
            self._api = pybitflyer.API(
                self._parameters._config['apikey'], self._parameters._config['secret'])
            self._order = bforder.order(
                self._logger, self._api, self._parameters, self, server_mode=True)
        else:
            self._order = None

        # データ保管用
        self._database = {}
        self._last_base_value = {}

        # データ更新中ロック
        self.lock = Lock()

        self.api = 0
        self._pos_history = {}
        self._today = -1
        self._minute = -1

        self._profit_history = deque(maxlen=1440)  # 1分毎、24H分の損益履歴

    # ポジション履歴のプロット & discordへの通知
    def plot_position_graph(self, position_history, image_file):
        history_time = [datetime.fromtimestamp(p[0]) for p in position_history]
        price = [p[1] for p in position_history]
        profit = [p[2] for p in position_history]
        position = [p[3] for p in position_history]
        api_count = [p[4] for p in position_history]

        fig = plt.figure()
        fig.autofmt_xdate()
        fig.tight_layout()

        # サブエリアの大きさの比率を変える
        gs = matplotlib.gridspec.GridSpec(
            nrows=2, ncols=1, height_ratios=[7, 3])
        ax1 = plt.subplot(gs[0])  # 0行0列目にプロット
        ax2 = ax1.twinx()
        ax2.tick_params(labelright=False)
        bx1 = plt.subplot(gs[1])  # 1行0列目にプロット
        bx1.tick_params(labelbottom=False)
        bx2 = bx1.twinx()

        # 上側のグラフ
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax1.set_ylim(
            [min(price) - 100 - (max(price)-min(price))/5, max(price) + 100])
        ax1.plot(history_time, price, label="market price")

        ax2.plot(history_time, api_count, label="API access", color='red')
        ax2.hlines(
            y=500, xmin=history_time[0], xmax=history_time[-1], colors='k', linestyles='dashed')
        ax2.set_ylim([0, 2800])
        ax2.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(500))

        # 損益の推移
        bx1.plot(history_time, profit, label="profit", color='red')
        bx1.set_ylim([min(profit) - 50, max(profit) + 50])
        bx1.get_yaxis().get_major_formatter().set_useOffset(False)
        bx1.get_yaxis().set_major_locator(ticker.MaxNLocator(integer=True))

        # ポジション推移
        if max(position) != max(position):
            bx2.set_ylim([-max(position) * 1.1, max(position) * 1.1])
        bx2.bar(history_time, position, width=0.001, label="position")
        bx2.hlines(
            y=0, xmin=history_time[0], xmax=history_time[-1], colors='k', linestyles='dashed')
        bx2.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(0.1))

        bx1.patch.set_alpha(0)
        bx1.set_zorder(2)
        bx2.set_zorder(1)

        # 凡例
        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        h3, l3 = bx1.get_legend_handles_labels()
        h4, l4 = bx2.get_legend_handles_labels()
        ax1.legend(h1, l1, loc='upper left', prop={'size': 8})
        ax2.legend(h2, l2, loc='lower left', prop={'size': 8})
        bx1.legend(h3+h4, l3+l4, loc='upper left', prop={'size': 8})

        ax1.grid(linestyle=':')
        bx1.grid(linestyle=':', which='minor')

        plt.savefig(image_file)
        plt.close()

    def __plot_plofit_graph_bfcolor(self, image_file):

        profit_history = list(self._profit_history)

        times_history = [s[0] for s in profit_history]
        price_history_raw = [s[1] for s in profit_history]
        price_history = list(pandas.Series(price_history_raw).rolling(
            window=20, min_periods=1).mean())
        price_history[-1] = price_history_raw[-1]

        fig = plt.figure()
        fig.autofmt_xdate()
        fig.tight_layout()
        ax = fig.add_subplot(111, facecolor='#fafafa')
        ax.spines['top'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(which='major', linestyle='-',
                color='#101010', alpha=0.1, axis='y')
        ax.tick_params(width=0, length=0)
        ax.tick_params(axis='x', colors='#c0c0c0')
        ax.tick_params(axis='y', colors='#c0c0c0')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))

        green1 = '#10b285'
        green2 = '#9cdcd0'
        red1 = '#e25447'
        red2 = '#f0b8b8'

        if price_history[-1] >= 0:
            ax.set_title(
                '{:+,.0f}'.format(price_history[-1]), color=green1, fontsize=28)
        else:
            ax.set_title(
                '{:+,.0f}'.format(price_history[-1]), color=red1, fontsize=28)

        last = 0
        plus_times = []
        plus_price = []
        minus_times = []
        minus_price = []
        for i in range(0, len(times_history)):

            if last * price_history[i] >= 0:
                if price_history[i] >= 0:
                    plus_times.append(datetime.fromtimestamp(times_history[i]))
                    plus_price.append(price_history[i])
                if price_history[i] <= 0:
                    minus_times.append(
                        datetime.fromtimestamp(times_history[i]))
                    minus_price.append(price_history[i])
            else:
                cross_point = price_history[i-1]/(price_history[i-1]-price_history[i])*(
                    times_history[i]-times_history[i-1])+times_history[i-1]
                if price_history[i] < 0:
                    plus_times.append(datetime.fromtimestamp(cross_point))
                    plus_price.append(0)
                    ax.plot(plus_times, plus_price,
                            color=green1, linewidth=0.8)
                    ax.fill_between(plus_times, plus_price, 0,
                                    color=green2, alpha=0.25)
                    plus_times = []
                    plus_price = []
                    minus_times = []
                    minus_price = []
                    minus_times.append(datetime.fromtimestamp(cross_point))
                    minus_price.append(0)
                    minus_times.append(
                        datetime.fromtimestamp(times_history[i]))
                    minus_price.append(price_history[i])
                else:
                    minus_times.append(datetime.fromtimestamp(cross_point))
                    minus_price.append(0)
                    ax.plot(minus_times, minus_price,
                            color=red1, linewidth=0.8)
                    ax.fill_between(minus_times, minus_price,
                                    0, color=red2, alpha=0.25)
                    plus_times = []
                    plus_price = []
                    minus_times = []
                    minus_price = []
                    plus_times.append(datetime.fromtimestamp(cross_point))
                    plus_price.append(0)
                    plus_times.append(datetime.fromtimestamp(times_history[i]))
                    plus_price.append(price_history[i])
            last = price_history[i]

        if len(plus_times) > 0:
            ax.plot(plus_times, plus_price, color=green1, linewidth=0.8)
            ax.fill_between(plus_times, plus_price, 0,
                            color=green2, alpha=0.25)

        if len(minus_times) > 0:
            ax.plot(minus_times, minus_price, color=red1, linewidth=0.8)
            ax.fill_between(minus_times, minus_price,
                            0, color=red2, alpha=0.25)

        plt.savefig(image_file, facecolor='#fafafa')
        plt.close()

        return price_history[-1]

    def _send_discord(self, message, image_file=None):
        try:
            if self._parameters._config['pos_server_discord'] != '':
                payload = {'content': ' {} '.format(message)}
                if image_file == None:
                    r = requests.post(
                        self._parameters._config['pos_server_discord'], data=payload, timeout=10)
                else:
                    try:
                        file = {'imageFile': open(image_file, "rb")}
                        r = requests.post(
                            self._parameters._config['pos_server_discord'], data=payload, files=file, timeout=10)
                    except:
                        r = requests.post(
                            self._parameters._config['pos_server_discord'], data=payload, timeout=10)
                if r.status_code == 204:
                    # 正常終了
                    return
                elif r.status_code == 404:
                    self._logger.error('Discord URL is not exist')
        except Exception as e:
            self._logger.error('Failed sending image to Discord: {}'.format(e))
            time.sleep(1)

    def com_read(self):
        # 通信の確立
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = self._parameters._config['pos_server'][0]
        if addr != 'localhost' and addr != '127.0.0.1':
            addr = '0.0.0.0'
        udp_sock.bind((addr, self._parameters._config['pos_server'][1]))

        while True:
            # UDPパケットの受信
            packet, addr = udp_sock.recvfrom(MAX_MESSAGE)

            # 受信データのデコード
            message = packet.decode('utf-8')
            product = message[0:11]
            pos = float(message[12:29])
            base = float(message[30:47])
            profit = int(message[48:59])
            api1 = int(message[60:65])
            api2 = int(message[66:71])
            strategy = message[73:]

            with self.lock:
                if product not in self._database:
                    self._database[product] = {}
                self._database[product][strategy] = {
                    'pos': pos, 'base': base, 'profit': profit, 'api1': api1, 'api2': api2, 'timestamp': time.time()}
            self._logger.debug("{} : {} : {}".format(
                product, strategy, self._database[product][strategy]))

        # 通信の終了
        udp_sock.close()
        self._logger.info('end of receiver')

    def api_server(self):
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = self._parameters._config['pos_server'][0]
        if addr != 'localhost' and addr != '127.0.0.1':
            addr = '0.0.0.0'
        tcp_sock.bind((addr, self._parameters._config['pos_server'][1]))
        while True:
            tcp_sock.listen(10)
            cl, addr = tcp_sock.accept()
            while True:
                try:
                    packet = cl.recv(MAX_MESSAGE)
                    mess = packet.decode('utf-8')
                    cl.sendall(str(self.api).encode('utf-8'))  # 現在のトータルapiを返す

                except socket.error:
                    cl.close()
                    break

    def _market_buy(self, size, nocheck=False):
        if self._order == None:
            return
        self._order._product_code = self._parameters._config['product']
        id = self._order.buy_order_market(size=size, nocheck=nocheck)
        self._logger.info(
            '        MARKET BUY!!! (size:{:.8f} {})'.format(size, id))
        return id

    def _market_sell(self, size, nocheck=False):
        if self._order == None:
            return
        self._order._product_code = self._parameters._config['product']
        id = self._order.sell_order_market(size=size, nocheck=nocheck)
        self._logger.info(
            '        MARKET SELL!!! (size:{:.8f} {})'.format(size, id))
        return id

    def summarize_position(self):
        def time_in_range(start, end, x):
            if start <= end:
                return start <= x <= end
            else:
                return start <= x or x <= end

        influx_client = None
        if 'pos_server_discord_influxdb' in self._parameters._config:
            try:
                influx_client = InfluxDBClient(
                    host=self._parameters._config['pos_server_discord_influxdb'][0], port=self._parameters._config['pos_server_discord_influxdb'][1], database='bots')
                influx_client.query('show measurements')
            except Exception as e:
                print(e)
                influx_client = None

        datas = {}
        last_position_diff = {}

        last_profit = {}  # botごとの前回の損益額

        self.api_pending_time = time.time()
        counter = 0
        while True:
            time.sleep(1)
            counter += 1
            with self.lock:
                for product, data in self._database.items():
                    for key, value in data.items():
                        if time.time()-value['timestamp'] > 300:
                            del self._database[product][key]
                            datas = {}
                            break

                for product, data in self._database.items():
                    if data == {}:
                        continue

                    if product in self._last_base_value.keys():
                        datas[product] = {'pos': 0.0, 'profit': 0, 'api1': 0,
                                          'api2': 0, 'base': self._last_base_value[product]}
                    else:
                        datas[product] = {'pos': 0.0, 'profit': 0,
                                          'api1': 0, 'api2': 0, 'base': 0.0}
                    for key, value in data.items():
                        if counter % 30 == 0:
                            self._logger.info("{} : api1({:>3}) : api2({:>3}) : profit({:>+7.0f}) : Pos({:>+11.8f}) : Base({:+f}) : {:.1f} : {}".format(
                                product,
                                value['api1'],
                                value['api2'],
                                value['profit'],
                                value['pos'],
                                value['base'],
                                time.time()-value['timestamp'],
                                key))

                            # 損益をInfluxに保存
                            if key not in last_profit:
                                last_profit[key] = value['profit']
                            if influx_client != None:
                                influx_data = [{"measurement": "bot_profit",
                                                "tags": {'bot': key, },
                                                "fields": {'profit': value['profit'],
                                                           'profit_diff': value['profit']-last_profit[key],
                                                           'position': value['pos'],
                                                           'apicount': value['api1'],
                                                           }}]
                                try:
                                    start = datetime_time(0, 0, 0)
                                    end = datetime_time(0, 2, 0)
                                    now = datetime_time((datetime.utcnow(
                                    )+timedelta(hours=9)).hour, (datetime.utcnow()+timedelta(hours=9)).minute, 0)
                                    # 0:00～0:02はグラフに入れない
                                    if not time_in_range(start, end, now):
                                        influx_client.write_points(influx_data)
                                    last_profit[key] = value['profit']
                                except Exception as e:
                                    self._logger.exception("Error while exporting to InfluxDB : {}, {}".format(
                                        e, traceback.print_exc()))

                        datas[product]['pos'] += value['pos']
                        datas[product]['profit'] += value['profit']
                        datas[product]['api1'] = max(
                            datas[product]['api1'], value['api1'])
                        datas[product]['api2'] += value['api2']
                        if 'base' in datas[product] and datas[product]['base'] != value['base'] and datas[product]['base'] != 0:
                            self._logger.error('base_offset error')
                        datas[product]['base'] = value['base']
                        self._last_base_value[product] = value['base']

            if counter % 30 == 0:
                self._logger.info('-'*70)
                self._logger.info(
                    '                profit          position  (base             target   )           fromAPI         diff')

            api1 = api2 = 0
            total_profit = 0
            for product, data in datas.items():
                if data == {}:
                    continue

                self._parameters._config['product'] = product.strip()

                if counter % 30 == 0:
                    if self._parameters._config['product'] == 'BTC_JPY':
                        minimum_order_size = 0.001
                    else:
                        minimum_order_size = 0.01

                    if time.time() < self.api_pending_time:
                        self._logger.info('API pending time')
                        actual = data['pos']+data['base']
                    else:
                        if self._order == None:
                            actual = 0
                        else:
                            actual = self._order._getpositions_api() if time.time(
                            ) > self.api_pending_time else data['pos']+data['base']

                    position_diff = round(actual-data['pos']-data['base'], 8)
                    if product not in last_position_diff:
                        last_position_diff[product] = deque([0], maxlen=500)
                    last_position_diff[product].append(position_diff)
                    self._logger.info('{:>11}: {:>+9.0f} : {:>15.8f}  ({:>+f} ={:>15.8f}) : {:>15.8f} : {:+.8f} {}'.format(
                        product, data['profit'], data['pos'], data['base'], data['pos'] +
                        data['base'], actual, position_diff,
                        ' ' if (abs(position_diff) < minimum_order_size or self._order == None) else '****' if max(list(last_position_diff[product])[-4:]) == min(list(last_position_diff[product])[-4:]) else '***' if max(list(
                            last_position_diff[product])[-3:]) == min(list(last_position_diff[product])[-3:]) else '**' if max(list(last_position_diff[product])[-2:]) == min(list(last_position_diff[product])[-2:]) else '*'
                    ))

                    # 損益をInfluxに保存
                    if product.replace(' ', '') not in last_profit:
                        last_profit[product.replace(' ', '')] = data['profit']
                    if influx_client != None:
                        influx_data = [{"measurement": "bot_profit",
                                        "tags": {'bot': product.replace(' ', '')+str(self._parameters._config['pos_server'][1]), },
                                        "fields": {'profit': data['profit'],
                                                   'profit_diff': data['profit']-last_profit[product.replace(' ', '')],
                                                   'position': data['pos'],
                                                   }}]
                        try:
                            start = datetime_time(0, 0, 0)
                            end = datetime_time(0, 2, 0)
                            now = datetime_time((datetime.utcnow(
                            )+timedelta(hours=9)).hour, (datetime.utcnow()+timedelta(hours=9)).minute, 0)
                            if not time_in_range(start, end, now):  # 0:00～0:02はグラフに入れない
                                influx_client.write_points(influx_data)
                            last_profit[product.replace(
                                ' ', '')] = data['profit']
                        except Exception as e:
                            self._logger.exception("Error while exporting to InfluxDB : {}, {}".format(
                                e, traceback.print_exc()))

                    if product not in self._pos_history.keys():
                        self._pos_history[product] = deque(maxlen=int(
                            self._parameters._config['pos_server_graph_period']*120))

                    start = datetime_time(0, 0, 0)
                    end = datetime_time(0, 2, 0)
                    now = datetime_time((datetime.utcnow(
                    )+timedelta(hours=9)).hour, (datetime.utcnow()+timedelta(hours=9)).minute, 0)
                    if not time_in_range(start, end, now):  # 0:00～0:02はグラフに入れない
                        self._pos_history[product].append([time.time(),
                                                           self.spot_price if product.strip() == 'BTC_JPY' else self.fx_price,
                                                           data['profit'],
                                                           data['pos'],
                                                           self.api])
                        total_profit += data['profit']

                    if self._order != None:
                        # 4度続けてポジションがズレていれば成売買で補正行う
                        if max(list(last_position_diff[product])[-4:]) == min(list(last_position_diff[product])[-4:]) and abs(position_diff) >= minimum_order_size:
                            maxsize = self._parameters._config['adjust_max_size'] if 'adjust_max_size' in self._parameters._config else 100
                            if position_diff < 0:
                                self._market_buy(min(-position_diff,maxsize), nocheck=True)
                            else:
                                self._market_sell(min(position_diff,maxsize), nocheck=True)

                api1 = max(api1, data['api1'])
                api2 += data['api2']
#                api1 += sum(self._parameters.api_counter) # このプログラム自体のapiアクセス回数
                self.api = api1

            if counter % 30 == 0:
                self._logger.info(
                    '         api1 : {:.0f}   api2 : {:.0f}'.format(api1, api2))
                self._logger.info('-'*70)

            if counter % 60 == 0:
                self._profit_history.append(
                    [(datetime.utcnow()+timedelta(hours=9)).timestamp(), total_profit])

            current_minutes = int(time.time() / 60)
            if self._minute != current_minutes:
                self._minute = current_minutes
                # 一定期間ごとにプロット (profit_intervalが0ならば日付が変わったときだけ1回）
                if((self._parameters._config['pos_server_discord_interval'] == 0 and self._today != (datetime.utcnow()+timedelta(hours=9)).strftime("%d")) or
                        (self._parameters._config['pos_server_discord_interval'] != 0 and (current_minutes % self._parameters._config['pos_server_discord_interval']) == 0)):
                    for product, history in self._pos_history.items():
                        if len(history) > 4 and self._database[product] != {}:
                            self.plot_position_graph(history, 'position.png')
                            message = '{} ポジション通知 {}'.format(
                                (datetime.utcnow()+timedelta(hours=9)).strftime('%H:%M:%S'), product)
                            self._send_discord(message, 'position.png')

                            discord_send_str = ''
                            total_pf = 0
                            total_size = 0
                            for product, data in self._database.items():
                                for key, value in data.items():
                                    discord_send_str += "{} : api1({:>3}) : api2({:>3}) : profit({:>+7.0f}) : Pos({:>+11.8f}) : Base({:+f}) : {:.1f} : {}\n".format(
                                        product,
                                        value['api1'],
                                        value['api2'],
                                        value['profit'],
                                        value['pos'],
                                        value['base'],
                                        time.time() - value['timestamp'],
                                        key)
                                    total_pf += int(value['profit'])
                                    total_size += float(value['pos'])
                            discord_send_str += '-'*70
                            discord_send_str += 'TOTAL pf: {:>4}  size: {:>1.8f}'.format(
                                total_pf, round(total_size, 8))
                            if discord_send_str != '' and 'pos_server_discord_send_text' in self._parameters._config and self._parameters._config['pos_server_discord_send_text']:
                                self._send_discord(discord_send_str)

                    if len(self._profit_history) > 4 and 'pos_server_discord_bitflyer_color' in self._parameters._config and self._parameters._config['pos_server_discord_bitflyer_color']:
                        message = '{} 損益通知 Profit:{:+.0f}'.format((datetime.utcnow()+timedelta(
                            hours=9)).strftime('%H:%M:%S'), self.__plot_plofit_graph_bfcolor('profit.png'))
                        self._send_discord(message, 'profit.png')

                # 日付が変わったら損益をリセット
                if self._today != (datetime.utcnow()+timedelta(hours=9)).strftime("%d"):
                    self._today = (datetime.utcnow() +
                                   timedelta(hours=9)).strftime("%d")
                    self._pos_history = {}
                    self._profit_history.clear()
                    for key, value in last_profit.items():
                        last_profit[key] = 0  # botごとの前回の損益額をリセット

            if self._parameters._config['created_at'] != os.path.getmtime(self._parameters._config_file):
                self._parameters.load_config_file(
                    self._parameters._config_file)

    def run(self):
        self.spot_price = 0
        self.fx_price = 0
        ticker = WebsocketTicks(self)

        # パケットの受信を別スレッドで起動
        thread_p = Thread(target=self.com_read)
        thread_p.start()

        # 集計と修正スレッドを起動
        thread_s = Thread(target=self.summarize_position)
        thread_s.start()

        # 集計と修正スレッドを起動
        thread_a = Thread(target=self.api_server)
        thread_a.start()

        while True:
            time.sleep(1)
            self._parameters.api_counter.append(0)  # apiカウンターを1秒ごとにシフトさせる
            update_filehandler(self._logger)


# ^Cが押されたときに行う停止処理
def quit_loop(signal, frame):
    os._exit(0)


if __name__ == "__main__":

    # ^Cが押されたときのハンドラを登録
    signal.signal(signal.SIGINT, quit_loop)

    # ポジション管理サーバークラス
    server = position_server()
    server.run()
