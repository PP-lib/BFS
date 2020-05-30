# -*- coding: utf-8 -*-

import sys
from libs import cryptowatch
from libs.base_strategy import Strategy
import importlib.machinery as imm
import time
import dateutil.parser
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

exec_debug = True


def setup_logger():
    logger = getLogger(__name__)
    handler = StreamHandler()
    handler.setLevel(INFO)
    logger.setLevel(INFO)
    logger.addHandler(handler)
    return logger


def plot_graph(df, filename='', title=''):

    price_values = df["price"]
    pos_values = df["pos"]
    pnl_values = df["pnl"]
    history_time = df["time"]

    fig = plt.figure()
    fig.autofmt_xdate()
    fig.tight_layout()

    # サブエリアの大きさの比率を変える
    gs = mpl.gridspec.GridSpec(nrows=3, ncols=1, height_ratios=[4, 4, 2])
    ax = plt.subplot(gs[0])  # 0行0列目にプロット
    ax.tick_params(labelbottom=False)
    bx = plt.subplot(gs[1])  # 1行0列目にプロット
    cx = plt.subplot(gs[2])  # 2行0列目にプロット
    cx.tick_params(labelbottom=False)

    # グラフタイトル
    if title != '':
        fig.suptitle(title, fontsize=9)

    pd.plotting.register_matplotlib_converters()

    # 上段のグラフ
    ax.set_ylim([min(price_values) - 5, max(price_values) + 5])
    ax.plot(history_time, price_values, label="market price")

    # 中段のグラフ
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

    for i, item in enumerate(bx.get_xticklabels()):
        fontsize = 6
        item.set_fontsize(fontsize)

    if filename != '':
        plt.savefig(filename)
    else:
        plt.show()
    plt.close()

# バックテスト用クラス


class backtest:

    def __init__(self, logger, config):
        self._logger = logger
        self._config = config

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

    def run(self, candle):
        self._minimum_order_size = 0.01

        starttime = time.time()

        # ロジックの初期化
        if self.initialize_func != None:
            self._strategy.initialize()

        # 初期化処理
        self.exec_price = 0  # 取得価格 x サイズ
        self.pos = 0  # ポジション情報
        self.hit = 0  # 約定回数
        self.pnl = 0

        time_list = []
        price_list = []
        pos_list = []
        pnl_list = []

        # START時点からEND時点までのループ
        for i in range(int(self.strategy_config['cryptowatch_candle']/self.strategy_config['backtest_resolution'])*self.strategy_config['cryptowatch_numOfCandle'], len(candle)):
            self._current_index = i
            self.current_candle = candle.head(self._current_index+1)
            candle_time = self.current_candle.index[-1]
            self.now_time = candle_time.timestamp()
            self.exec_date = str(candle_time)
            self._ltp = self.current_candle["open"][-1]

            # ロスカットチェック
            self._strategy.loss_cut_check()

            # 売買判断
            self._strategy.logic()

            self.pnl = self.exec_price + self.pos * self._ltp  # 損益を計算し、Numpy Ndarrayに保存
            time_list.append(candle_time)
            price_list.append(self._ltp)
            pos_list.append(self.pos)
            pnl_list.append(self.pnl)
#            print( candle_time, self._ltp, self.pos, self.pnl )

        if len(pos_list) != 0:
            maxpos = round(max(pos_list), 2)  # 最大Buyポジション
            minpos = round(min(pos_list), 2)  # 最大Sellポジション
        else:
            maxpos = minpos = 0

        param_str = ''
        for key, value in self.strategy_config['parameters'].items():
            if type(value) is float:
                value = round(value, 8)
            if type(value) is np.float64:
                value = round(value, 8)
            param_str += '{} {} /'.format(key, value)
        result_str = 'PnL:{} /MaxPos:{:.2f} /MinPos:{:.2f} /order:{}'.format(
            0 if len(pnl_list) == 0 else int(pnl_list[-1]), maxpos, minpos, self.hit)
        self._logger.info("{}{}".format(param_str, result_str))
        self._logger.info("{:.3f}sec".format(time.time() - starttime))

        return {"time": time_list, "price": price_list, "pos": pos_list, "pnl": pnl_list}, param_str[:-2], 0 if len(pnl_list) == 0 else round(int(pnl_list[-1])/max(abs(maxpos), abs(minpos)))

    def _get_cryptowatch(self):
        # ターゲットの時間軸に変換
        self.target_candle = self.current_candle.resample(str(self.strategy_config['cryptowatch_candle']*60)+"s").agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', "volume": "sum"}).tail(self.strategy_config['cryptowatch_numOfCandle'])
        return self.target_candle

    @property
    def _is_backtesting(self):
        return True

    @property
    def _pos(self):
        return self.pos

    @property
    def _profit(self):
        return self.pnl

    @property
    def _profit_unreal(self):
        return 0

    @property
    def _api_count(self):
        return 0

    @property
    def _server_latency(self):
        return 0

    @property
    def _server_latency_rate(self):
        return 0

    @property
    def _server_health(self):
        return 'NORMAL'

    def _market_buy(self, size, nocheck=False):
        price = self._ltp + self.strategy_config['slipage']
        self.hit += 1
        self.pos += size  # ポジションを増やす
        self.exec_price -= price * size  # 取得価格の更新
        self.pnl = self.exec_price + self.pos * price  # 損益を計算し、Numpy Ndarrayに保存
        if exec_debug:
            self._logger.info('        {} BUY!!!  (market price:{:.0f} size:{:+.3f} pos:{:+.3f} pnl:{:+.0f})'.format(
                self.exec_date, price, size, self.pos, self.pnl))

        return True

    def _market_sell(self, size, nocheck=False):
        price = self._ltp - self.strategy_config['slipage']
        self.hit += 1
        self.pos -= size  # ポジションを減らす
        self.exec_price += price * size  # 取得価格の更新
        self.pnl = self.exec_price + self.pos * price  # 損益を計算し、Numpy Ndarrayに保存
        if exec_debug:
            self._logger.info('        {} SELL!!! (market price:{:.0f} size:{:+.3f} pos:{:+.3f} pnl:{:+.0f})'.format(
                self.exec_date, price, -size, self.pos, self.pnl))

        return True

    def _close_position(self):
        if self._pos >= self._minimum_order_size:
            id = self._strategy._market_sell(self._pos)
            return True
        elif self._pos <= -self._minimum_order_size:
            id = self._strategy._market_buy(-self._pos)
            return True

    def logic(self):
        return


if __name__ == '__main__':

    # loggerの準備
    logger = setup_logger()

    # configファイル読み込み
    config = yaml.safe_load(
        open('backtest_cryptowatch.yaml', 'r', encoding='utf-8_sig'))

    # 引数の処理
    if len(sys.argv) == 3:
        config['strategy_py'] = sys.argv[1]
        config['strategy_yaml'] = sys.argv[2]

    # バックテスト初期化
    backtest = backtest(logger, config)
    backtest.strategy_config["backtest_resolution"] = config['backtest_resolution']
    backtest.strategy_config["slipage"] = config['slipage']

    # CryptoWatchデータ取得
    market = 'bitflyer/btcfxjpy'
    cw = cryptowatch.CryptoWatch()
    candle = cw.getCandle(config['backtest_resolution']*60,
                          market, numofcandle=config['backtest_candles'], fill=True)
    print("{} candles".format(len(candle)))
    print("First Candle : {}".format(candle.index[1]))

    backtest_done = False
    if 'optimize' in config and config['optimize'] != None:
        for key, value in config['optimize'].items():
            if key not in backtest.strategy_config['parameters']:
                print("{} is not in parameters".format(key))
            else:
                original = backtest.strategy_config['parameters'][key]
                x = np.arange(value[0], value[1], value[2])
                print("key:{} = {}".format(key, x))
                result = []
                for i in x:
                    backtest.strategy_config['parameters'][key] = i

                    # バックテスト実施
                    dft, title, profit = backtest.run(candle)
                    # グラフのプロット
                    plot_graph(dft, title=title, filename=title.replace(
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
        dft, title, profit = backtest.run(candle)
        # グラフのプロット
        plot_graph(dft, title=title, filename=config['output_files'])
