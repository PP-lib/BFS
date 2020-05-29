# coding: utf-8
import pandas
import json
import requests
from datetime import datetime, timedelta, timezone
import time


class CryptoWatch:

    _supported_term = [3600, 1800, 900, 300, 180, 60]

    def getOriginalCandle(self, timeframe, market, numofcandle):
        after = round(time.time())-(timeframe*numofcandle)
        url = 'https://api.cryptowat.ch/markets/{}/ohlc?after={:.0f}&periods={}'.format(
            market, after, timeframe)
        response = requests.get(url).json()
        cryptowath_candle = response['result'][str(timeframe)]

        try:
            print('cost:{} remaining:{} ({:.1f}times)'.format(
                response["allowance"]["cost"], response["allowance"]["remaining"], response["allowance"]["remaining"]/response["allowance"]["cost"]))
        except:
            pass
        candle_pd = pandas.DataFrame([[datetime.fromtimestamp(c[0]-timeframe, timezone(timedelta(hours=9), 'JST')), c[1], c[2], c[3], c[4], c[5]]
                                      for c in cryptowath_candle if c[4] != 0], columns=["date", "open", "high", "low", "close", "volume"])
        return candle_pd

    def getCandle(self, timeframe, market, numofcandle, fill=False):
        for t in self._supported_term:
            # Cryptowatchがサポートしている時間足で割り切れる時間を探す
            if timeframe >= t and (timeframe % t) == 0:

                # Cryptowatchから取得
                original_candle_pd = self.getOriginalCandle(
                    t, market, int(numofcandle*timeframe/t)+1)

                # ターゲットの時間軸に変換
                target_candle = original_candle_pd.set_index('date').resample(str(timeframe)+"s").agg(
                    {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', "volume": "sum"})

                if fill == True:
                    # 欠損データの補完(4時のメンテナンス時など）
                    candle_index = target_candle.index.values
                    for i in range(1, len(candle_index)):
                        # NaNが自身との等号判定でfalseを返すという性質を利用してNanかどうかを判定
                        if target_candle.at[candle_index[i], "open"] != target_candle.at[candle_index[i], "open"]:
                            # その期間に約定履歴が無い場合にはひとつ前の足からコピー
                            target_candle.loc[candle_index[i], [
                                "open", "high", "low", "close"]] = target_candle.at[candle_index[i-1], "close"]
                else:
                    # 欠損データの削除(4時のメンテナンス時など）
                    target_candle = target_candle.dropna()

                return target_candle[-min(len(target_candle), numofcandle):]
