# -*- coding: utf-8 -*-

from logging import getLogger, INFO, StreamHandler, FileHandler
import csv
import numpy as np
import yaml
import backtest_scalpingmode as backtest_module
yaml_file = "backtest_scalpingmode.yaml"
csv_file = "backtest_scalpingmode_result.csv"
plot_graph = True


NOTICE = 25  # INFO(20)よりはレベルが上のログ

if __name__ == '__main__':

    # configファイル読み込み
    config = yaml.safe_load(
        open(yaml_file, 'r', encoding='utf-8_sig'))

    # loggerの準備
    logger = getLogger(__name__)
    logger.setLevel(INFO)
    handler = StreamHandler()
    handler.setLevel(INFO)
    logger.addHandler(handler)

    # バックテスト初期化
    backtest = backtest_module.backtest(logger, config)

    # 約定履歴の読み込み
    df = backtest_module.load_cvs_files(logger, config)

    # パラメータの最適化組み合わせ無しの場合
    if config['optimize'] == None:
        # バックテスト実施
        dft, title, profit = backtest.run(df)

        if plot_graph:
            # グラフのプロット
            backtest_module.plot_graph(
                dft, title=title, filename=config['output_files'])

    # 組み合わせテストを行う場合
    else:
        # 組み合わせテストを行うときには、バックテストの途中経過を表示させない
        logger.setLevel(NOTICE)

        def flatten(x): return [z for y in x for z in (
            flatten(y) if hasattr(y, '__iter__') and not isinstance(y, str) else (y,))]
        key_ar = []
        value_hs = {}

        for key, value in config['optimize'].items():
            key_ar.append(key)
            value_hs[key] = np.arange(value[0], value[1], value[2])
            print("key:{} = {}".format(key, value_hs[key]))

        param_ar = value_hs[key_ar[0]]

        for i in range(len(key_ar)-1):
            param_ar = [[x, y]
                        for x in param_ar for y in value_hs[key_ar[i+1]]]
            if i > 0:
                for i2 in range(len(param_ar)):
                    param_ar[i2] = flatten(param_ar[i2])

        print("len(param_ar)", len(param_ar))
        result = []
        x = range(0, len(param_ar))

        count = 0
        for value_ar in param_ar:
            print(key_ar, "=", value_ar)
            for key in key_ar:
                if len(key_ar) == 1:
                    backtest.strategy_config["parameters"][key] = value_ar
                else:
                    backtest.strategy_config["parameters"][key] = value_ar[key_ar.index(
                        key)]
            # 当該パラメータのバックテスト実施
            dft, title, profit = backtest.run(df)
            count += 1
            logger.log(NOTICE, "{}/{} : {} PNL:{:.0f}".format(count,
                                                              len(param_ar), title, profit))

            if plot_graph:
                # グラフのプロット
                backtest_module.plot_graph(
                    dft, title=title, filename=title.replace('/', '').replace(':', '')+'.png')

            # 結果をファイルへ書き出し
            tmp_title = str(title.replace('_/', '_').replace(':', '_'))
            tmp_profit = str(profit)
            with open(csv_file, 'a', newline='') as fff:
                writer = csv.writer(fff)
                writer.writerow(title.split()+[tmp_profit])
