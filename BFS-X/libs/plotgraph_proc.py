# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import random
from statistics import median
from threading import Lock
from datetime import datetime, timedelta
import time
import requests
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def median2(q):
    return median(q) if len(q) != 0 else 0


class PositionGraphThread:
    def __init__(self, logger):
        self.procs_lock = Lock()
        self._logger = logger

    def plot_position_graph_thread(self, history_time, price, average, leverage,
                                   position, normal, very_busy, super_busy,
                                   profit, api_count, api_order,
                                   image_file, config_file, position_discord_webhooks, wait):

        self._logger.debug('[plot] plot_position_graph called' )
        if not self.procs_lock.locked():
            with self.procs_lock:
                time.sleep(wait)

        with self.procs_lock:
            self._logger.debug('[plot] plot_position_graph started' )

            fig = plt.figure()
            fig.autofmt_xdate()
            fig.tight_layout()

            time.sleep(random.uniform(1.0, 3.0))
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
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax1.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.0f'))
            ax1.set_ylim([min(price + average) - 100 - (max(price + average) -
                                                        min(price + average))/5, max(price + average) + 100])
            time.sleep(random.uniform(1.0, 3.0))
            ax1.plot(history_time, price, label="market price")
            ax1.plot(history_time, average, label="position average")
            ax1.bar(history_time, normal, color='green',
                    width=0.001, alpha=0.1)
            ax1.bar(history_time, very_busy,
                    color='red', width=0.001, alpha=0.1)
            ax1.bar(history_time, super_busy,
                    color='red', width=0.001, alpha=0.5)

            ax2.plot(history_time, api_count, label="API", color='red')
            ax2.plot(history_time, api_order,
                     label="API order", color='orange')
            ax2.hlines(
                y=500, xmin=history_time[0], xmax=history_time[-1], colors='k', linestyles='dashed')
            ax2.set_ylim([0, 2800])
            ax2.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(500))

            time.sleep(random.uniform(1.0, 3.0))
            # 損益の推移
            bx1.plot(history_time, profit, label="profit", color='red')
            bx1.set_ylim([min(profit) - 50, max(profit) + 50])
            bx1.get_yaxis().get_major_formatter().set_useOffset(False)
            bx1.get_yaxis().set_major_locator(ticker.MaxNLocator(integer=True))

            # ポジション推移
            if max(leverage) != max(leverage):
                bx2.set_ylim([-max(leverage) * 1.1, max(leverage) * 1.1])
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

            time.sleep(random.uniform(1.0, 3.0))
            plt.savefig(image_file)
            plt.close()

            time.sleep(random.uniform(1.0, 3.0))
            try:
                message = '{} ポジション通知 {}'.format(
                    (datetime.utcnow()+timedelta(hours=9)).strftime('%H:%M:%S'), config_file)

                if position_discord_webhooks != '':
                    file = {'imageFile': open(image_file, "rb")}
                    payload = {'content': ' {} '.format(message)}
                    requests.post(position_discord_webhooks,
                                  data=payload, files=file, timeout=10)

            except Exception as e:
                self._logger.error(
                    'Failed sending image to Discord: {}'.format(e))

            self._logger.debug('[plot] plot_position_graph finished' )

    def plot_plofit_graph_bfcolor_thread(self, history_timestamp, price_history, average, fmt, rotate, image_file, discord_webhook, wait):

        self._logger.debug('[plot] plot_plofit_graph_bfcolor called' )
        if not self.procs_lock.locked():
            with self.procs_lock:
                time.sleep(wait)

        with self.procs_lock:
            self._logger.debug('[plot] plot_plofit_graph_bfcolor started' )

            fig = plt.figure()
            fig.autofmt_xdate()
            fig.tight_layout()

            time.sleep(random.uniform(1.0, 3.0))
            ax = fig.add_subplot(111, facecolor='#fafafa')
            ax.spines['top'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.spines['left'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(which='major', linestyle='-',
                    color='#101010', alpha=0.1, axis='y')
            if rotate == 0:
                ax.tick_params(width=0, length=0)
            else:
                ax.tick_params(width=1, length=5)
            ax.tick_params(axis='x', colors='#c0c0c0')
            ax.tick_params(axis='y', colors='#c0c0c0')
            if fmt != '':
                ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))

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

            time.sleep(random.uniform(1.0, 3.0))
            last = 0
            plus_times = []
            plus_price = []
            minus_times = []
            minus_price = []
            for i in range(0, len(history_timestamp)):

                if last * price_history[i] >= 0:
                    if price_history[i] >= 0:
                        plus_times.append(
                            datetime.fromtimestamp(history_timestamp[i]))
                        plus_price.append(price_history[i])
                    if price_history[i] <= 0:
                        minus_times.append(
                            datetime.fromtimestamp(history_timestamp[i]))
                        minus_price.append(price_history[i])
                else:
                    cross_point = price_history[i-1]/(price_history[i-1]-price_history[i])*(
                        history_timestamp[i]-history_timestamp[i-1])+history_timestamp[i-1]
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
                            datetime.fromtimestamp(history_timestamp[i]))
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
                        plus_times.append(
                            datetime.fromtimestamp(history_timestamp[i]))
                        plus_price.append(price_history[i])
                last = price_history[i]

            time.sleep(random.uniform(1.0, 3.0))
            if len(plus_times) > 0:
                ax.plot(plus_times, plus_price, color=green1, linewidth=0.8)
                ax.fill_between(plus_times, plus_price, 0,
                                color=green2, alpha=0.25)

            if len(minus_times) > 0:
                ax.plot(minus_times, minus_price, color=red1, linewidth=0.8)
                ax.fill_between(minus_times, minus_price,
                                0, color=red2, alpha=0.25)

            labels = ax.get_xticklabels()
            plt.setp(labels, rotation=rotate)

            time.sleep(random.uniform(1.0, 3.0))
            plt.savefig(image_file, facecolor='#fafafa')
            plt.close()

            time.sleep(random.uniform(1.0, 3.0))
            try:
                message = '{} 損益通知 Profit:{:+.0f}'.format(
                    (datetime.utcnow()+timedelta(hours=9)).strftime('%H:%M:%S'), price_history[-1])

                if discord_webhook != '':
                    file = {'imageFile': open(image_file, "rb")}
                    payload = {'content': ' {} '.format(message)}
                    requests.post(discord_webhook, data=payload,
                                  files=file, timeout=10)

            except Exception as e:
                self._logger.error(
                    'Failed sending image to Discord: {}'.format(e))

            self._logger.debug('[plot] plot_plofit_graph_bfcolor finished' )

    def plot_plofit_graph_thread(self, history_time, price_values, fixed_pnl_values,
                                 pnl_values, pos_values, sfd_values,
                                 disp_position, disp_realized_profit,
                                 image_file, discord_webhook, wait):

        self._logger.debug('[plot] plot_plofit_graph called' )
        if not self.procs_lock.locked():
            with self.procs_lock:
                time.sleep(wait)

        with self.procs_lock:
            self._logger.debug('[plot] plot_plofit_graph started' )

            fig = plt.figure()
            fig.autofmt_xdate()
            fig.tight_layout()

            time.sleep(random.uniform(1.0, 3.0))
            # サブエリアの大きさの比率を変える
            if disp_position:
                gs = matplotlib.gridspec.GridSpec(
                    nrows=3, ncols=1, height_ratios=[4, 4, 2])
            else:
                gs = matplotlib.gridspec.GridSpec(
                    nrows=2, ncols=1, height_ratios=[7, 3])
            ax = plt.subplot(gs[0])  # 0行0列目にプロット
            ax.tick_params(labelbottom=False)
            bx = plt.subplot(gs[1])  # 1行0列目にプロット
            if disp_position:
                cx = plt.subplot(gs[2])  # 2行0列目にプロット
                cx.tick_params(labelbottom=False)

            time.sleep(random.uniform(1.0, 3.0))
            # 上段のグラフ
            ax.set_ylim([min(price_values) - 5, max(price_values) + 5])
            ax.plot(history_time, price_values, label="market price")
            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.0f'))

            time.sleep(random.uniform(1.0, 3.0))
            # 中段のグラフ
            bx.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            if max(sfd_values) != 0 or min(sfd_values) != 0:
                bx.set_ylim([min(min(pnl_values), min(sfd_values)) - 5,
                             max(max(pnl_values), max(sfd_values)) + 5])
            else:
                bx.set_ylim([min(pnl_values) - 5, max(pnl_values) + 5])
            bx.plot(history_time, pnl_values, color='red', label="profit")
            if disp_realized_profit:
                bx.plot(history_time, fixed_pnl_values,
                        color='orange', label="realized")

            if max(sfd_values) != 0 or min(sfd_values) != 0:
                bx.plot(history_time, sfd_values,
                        color='blue', label="SFD commission")

            time.sleep(random.uniform(1.0, 3.0))
            if disp_position:
                # 下段のグラフ
                cx.set_ylim([min(pos_values) * 1.1, max(pos_values) * 1.1])
                cx.plot(history_time, pos_values, label="position")
                cx.hlines(
                    y=0, xmin=history_time[0], xmax=history_time[-1], colors='k', linestyles='dashed')

            # 凡例
            h1, l1 = ax.get_legend_handles_labels()
            h2, l2 = bx.get_legend_handles_labels()
            if disp_position:
                h3, l3 = cx.get_legend_handles_labels()
            ax.legend(h1, l1, loc='upper left', prop={'size': 8})
            bx.legend(h2, l2, loc='upper left', prop={'size': 8})
            if disp_position:
                cx.legend(h3, l3, loc='upper left', prop={'size': 8})

            ax.grid(linestyle=':')
            bx.grid(linestyle=':')
            if disp_position:
                cx.grid(linestyle=':', which='minor')

            time.sleep(random.uniform(1.0, 3.0))
            plt.savefig(image_file)
            plt.close()

            time.sleep(random.uniform(1.0, 3.0))
            try:
                message = '{} 損益通知 Profit:{:+.0f}'.format(
                    (datetime.utcnow()+timedelta(hours=9)).strftime('%H:%M:%S'), pnl_values[-1])

                if discord_webhook != '':
                    file = {'imageFile': open(image_file, "rb")}
                    payload = {'content': ' {} '.format(message)}
                    requests.post(discord_webhook, data=payload,
                                  files=file, timeout=10)

            except Exception as e:
                self._logger.error(
                    'Failed sending image to Discord: {}'.format(e))

            self._logger.debug('[plot] plot_plofit_graph finished' )

    def plot_rate_graph_thread(self, history_time, profit_estimated, ordered_count, filled_count,
                               order_filled_rate, taked_count, order_taked_rate, slipage_history,
                               image_file, discord_webhook, wait):

        self._logger.debug('[plot] plot_rate_graph called' )
        if not self.procs_lock.locked():
            with self.procs_lock:
                time.sleep(wait)

        with self.procs_lock:
            self._logger.debug('[plot] plot_rate_graph started' )

            fig = plt.figure()
            fig.autofmt_xdate()
            fig.tight_layout()

            time.sleep(random.uniform(1.0, 3.0))
            # サブエリアの大きさの比率を変える
            gs = matplotlib.gridspec.GridSpec(
                nrows=3, ncols=1, height_ratios=[4, 3, 3])
            ax1 = plt.subplot(gs[0])  # 0行0列目にプロット
            ax2 = ax1.twinx()
            bx1 = plt.subplot(gs[1])  # 1行0列目にプロット
            bx1.tick_params(labelbottom=False)
            cx1 = plt.subplot(gs[2])  # 2行0列目にプロット
            cx1.tick_params(labelbottom=False)

            time.sleep(random.uniform(1.0, 3.0))
            # 上側のグラフ
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax1.plot(history_time, profit_estimated,
                     label="profit", color='red')
            ax1.set_ylim([min(profit_estimated) - 50,
                          max(profit_estimated) + 50])
            ax1.get_yaxis().get_major_formatter().set_useOffset(False)
            ax1.get_yaxis().set_major_locator(ticker.MaxNLocator(integer=True))

            if max(ordered_count) != 0:
                ax2.set_ylim([0, max(ordered_count) * 3])
            ax2.bar(history_time, ordered_count, width=0.001,
                    alpha=0.5, label="order count")
            ax1.patch.set_alpha(0)
            ax1.set_zorder(2)
            ax2.set_zorder(1)

            time.sleep(random.uniform(1.0, 3.0))
            # 中段のグラフ（損益の推移）
            bx1.set_ylim([min(order_filled_rate)-5, max(order_filled_rate)+5])
            bx1.plot(history_time, order_filled_rate,
                     label="filled rate (%)", color='orange')

            bx2 = bx1.twinx()
            if max(filled_count) != 0:
                bx2.set_ylim([0, max(filled_count) * 3])
            bx2.bar(history_time, filled_count, width=0.001,
                    alpha=0.5, label="filled count")
            bx1.patch.set_alpha(0)
            bx1.set_zorder(2)
            bx2.set_zorder(1)

            time.sleep(random.uniform(1.0, 3.0))
            # 中段のグラフ（損益の推移）
            cx1.set_ylim([min(order_taked_rate)-5, max(order_taked_rate)+5])
            cx1.plot(history_time, order_taked_rate,
                     label="taked rate (%)", color='orange')

            cx2 = cx1.twinx()

            if len(slipage_history) != 0:
                cx2.plot([s[0] for s in slipage_history], [s[1] for s in slipage_history], label="slipage",
                         color='blue', marker='o', alpha=0.5, linewidth=0)

            cx1.patch.set_alpha(0)
            cx1.set_zorder(2)
            cx2.set_zorder(1)

            # 凡例
            h1, l1 = ax1.get_legend_handles_labels()
            ax1.legend(h1, l1, loc='upper left', prop={'size': 8})

            h2, l2 = ax2.get_legend_handles_labels()
            ax2.legend(h2, l2, loc='upper right', prop={'size': 8})

            h3, l3 = bx1.get_legend_handles_labels()
            bx1.legend(h3, l3, loc='upper left', prop={'size': 8})

            h4, l4 = bx2.get_legend_handles_labels()
            bx2.legend(h4, l4, loc='upper right', prop={'size': 8})

            h5, l5 = cx1.get_legend_handles_labels()
            cx1.legend(h5, l5, loc='upper left', prop={'size': 8})

            h6, l6 = cx2.get_legend_handles_labels()
            cx2.legend(h6, l6, loc='upper right', prop={'size': 8})

            ax1.grid(linestyle=':')
            bx1.grid(linestyle=':')
            cx1.grid(linestyle=':')

            time.sleep(random.uniform(1.0, 3.0))
            plt.savefig(image_file)
            plt.close()

            time.sleep(random.uniform(1.0, 3.0))
            try:
                if discord_webhook != '':
                    file = {'imageFile': open(image_file, "rb")}
                    payload = {'content': ' Execute rate'}
                    requests.post(discord_webhook, data=payload,
                                  files=file, timeout=10)

            except Exception as e:
                self._logger.error(
                    'Failed sending image to Discord: {}'.format(e))

            self._logger.debug('[plot] plot_rate_graph finished in' )

    def plot_histgram_thread(self, list1, list2, list3, image_file, discord_webhook, wait):

        self._logger.debug('[plot] plot_histgram called' )
        if not self.procs_lock.locked():
            with self.procs_lock:
                time.sleep(wait)

        with self.procs_lock:
            self._logger.debug('[plot] plot_histgram started' )

            try:
                fig = plt.figure()
                fig.autofmt_xdate()
                fig.tight_layout()
                time.sleep(random.uniform(1.0, 3.0))
                ax = plt.subplot(1, 1, 1)
                ax.set_xlabel('response (msec)')
                ax.hist(list1, label='send order  {:.0f}msec'.format(
                    median2(list1)), bins=50, range=(20, 300), color='red', alpha=0.5, density=True)
                ax.hist(list2, label='get orders  {:.0f}msec'.format(median2(
                    list2)), bins=50, range=(20, 300), color='blue', alpha=0.5, density=True)
                ax.hist(list3, label='cancel order{:.0f}msec'.format(median2(
                    list3)), bins=50, range=(20, 300), color='green', alpha=0.5, density=True)
                ax.legend()
                time.sleep(random.uniform(1.0, 3.0))
                plt.savefig(image_file)
                plt.close()
            except Exception:
                self._logger.exception(
                    "Error while plotting response histogram : %s", Exception)

            time.sleep(random.uniform(1.0, 3.0))
            try:
                if discord_webhook != '':
                    file = {'imageFile': open(image_file, "rb")}
                    payload = {'content': ' API responce'}
                    requests.post(discord_webhook, data=payload,
                                  files=file, timeout=10)

            except Exception as e:
                self._logger.error(
                    'Failed sending image to Discord: {}'.format(e))

            self._logger.debug('[plot] plot_histgram finished' )

    def plot_latency_thread(self, server_order_delay_history, server_cancel_delay_history, server_latency_history,
                            latency_value, image_file, discord_webhook, wait):

        self._logger.debug('[plot] plot_latency called' )
        if not self.procs_lock.locked():
            with self.procs_lock:
                time.sleep(wait)

        with self.procs_lock:
            self._logger.debug('[plot] plot_latency started' )

            try:
                fig = plt.figure()
                fig.autofmt_xdate()
                fig.tight_layout()
                gs = matplotlib.gridspec.GridSpec(
                    nrows=2, ncols=1, height_ratios=[7, 3])

                time.sleep(random.uniform(1.0, 3.0))
                ax1 = plt.subplot(gs[0])  # 0行0列目にプロット
                bx1 = plt.subplot(gs[1])  # 1行0列目にプロット
                a = list(server_order_delay_history)
                if len(a) != 0:
                    ax1.plot([s[0] for s in a], [s[1] for s in a],
                             label="order delay", color='red', marker='o', linewidth=0)

                a = list(server_cancel_delay_history)
                if len(a) != 0:
                    ax1.plot([s[0] for s in a], [s[1] for s in a],
                             label="cancel daley", color='green', marker='s', linewidth=0)

                if len(server_order_delay_history)+len(server_cancel_delay_history) != 0:
                    ax1.xaxis.set_major_formatter(
                        mdates.DateFormatter('%H:%M'))
                    ax1.set_ylabel('msec')
                    ax1.legend()

                time.sleep(random.uniform(1.0, 3.0))
                a = list(server_latency_history)
                if len(a) != 0:
                    bx2 = bx1.twinx()
                    bx1.xaxis.set_major_formatter(
                        mdates.DateFormatter('%H:%M'))
                    bx2.xaxis.set_major_formatter(
                        mdates.DateFormatter('%H:%M'))
                    bx1.plot([s[0] for s in a], [s[1] for s in a],
                             label="latency {:.0f}msec".format(latency_value), color='blue', linewidth=3)
                    bx2.plot([s[0] for s in a], [s[2] for s in a],
                             label="market price", color='orange', linewidth=1)
                    bx1.set_ylabel('msec')
                    bx1.legend(loc='upper left')
                    bx2.legend(loc='upper right')

                time.sleep(random.uniform(1.0, 3.0))
                plt.savefig(image_file)
                plt.close()
            except Exception:
                self._logger.exception(
                    "Error while plotting response histogram : %s", Exception)

            time.sleep(random.uniform(1.0, 3.0))
            try:
                if discord_webhook != '':
                    file = {'imageFile': open(image_file, "rb")}
                    payload = {'content': ' Order event'}
                    requests.post(discord_webhook, data=payload,
                                  files=file, timeout=10)

            except Exception as e:
                self._logger.error(
                    'Failed sending image to Discord: {}'.format(e))

            self._logger.debug('[plot] plot_latency finished' )
