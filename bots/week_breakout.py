import asyncio
import sys

from bots.week_breakout_indicator import WeekIndicator
from futuremaker import utils, log
from futuremaker.binance_api import BinanceAPI
from futuremaker.bot import Bot
from futuremaker.algo import Algo
from futuremaker.position_type import Type, Yoil


class WeekBreakout(Algo):
    def __init__(self, base, quote, floor_decimals, init_capital, max_budget, commission_rate,
                 long_rate, short_rate, paper, buy_unit, buy_delay, week_start=Yoil.MON, hour_start=0):
        super().__init__(base=base, quote=quote, floor_decimals=floor_decimals, init_capital=init_capital,
                         max_budget=max_budget, commission_rate=commission_rate, paper=paper,
                         buy_unit=buy_unit, buy_delay=buy_delay)
        self.weekIndicator = WeekIndicator(week_start, hour_start, long_rate, short_rate)

    def ready(self):
        self.wallet_summary()

    def update_candle(self, df, candle, localtime):
        candle = self.weekIndicator.update(df, candle)

        long_entry = candle.open < candle.long_break < candle.close
        short_entry = candle.close < candle.short_break < candle.open
        time_condition = (localtime - self.position_entry_time).days >= 1

        explain = f'{localtime} ' \
                  f'position[{self.position_quantity:0.3f}] open[{candle.open:0.3f}] long[{candle.long_break:0.3f}] ' \
                  f'short[{candle.short_break:0.3f}] close[{candle.close:0.3f}] ' \
                  f'localtime[{localtime}] entry_time[{self.position_entry_time}]\n' \
                  f'long_entry[{long_entry}] short_entry[{short_entry}] time_condition[{time_condition}]'

        if not self.backtest:
            log.logger.info(explain)
            self.send_message(explain)

        # 1. candle 이 long_break 를 뚫으면 롱 포지션을 취한다.
        if candle.open < candle.long_break < candle.close:
            # 하루이상 지나야 매매한다.
            if (localtime - self.position_entry_time).days >= 1:
                if self.position_quantity < 0:
                    # 먼저 숏 포지션을 CLOSE 한다.
                    quantity = self.close_short()
                    self.calc_close(localtime, candle.close, self.position_entry_price, -quantity)
                # 롱 진입
                if self.position_quantity == 0:
                    self.open_long()
                    self.calc_open(Type.LONG, localtime, candle.close, candle.long_break)

        # 2. candle 이 short_break 를 뚫으면 숏 포지션을 취한다.
        # if candle.close < candle.short_break:
        if candle.close < candle.short_break < candle.open:
            if (localtime - self.position_entry_time).days >= 1:
                # short 수행.
                if self.position_quantity > 0:
                    quantity = self.close_long()
                    self.calc_close(localtime, candle.close, self.position_entry_price, quantity)
                    # 먼저 롱 포지션을 CLOSE 한다.
                # 숏 진입
                if self.position_quantity == 0:
                    self.open_short()
                    self.calc_open(Type.SHORT, localtime, candle.close, candle.short_break)

        # 3. 롱 포지션 손절.
        if self.position_quantity > 0:
            if candle.close < min(candle.long_break,
                                  self.position_losscut_price) < candle.open:  # 롱 라인을 뚫고 내려올때. min을 사용하여 좀더 여유확보.
                if (localtime - self.position_entry_time).days >= 1:
                    quantity = self.close_long()
                    self.calc_close(localtime, candle.close, self.position_entry_price, quantity)

        # 4. 숏 포지션 손절.
        if self.position_quantity < 0:
            if candle.close > min(candle.short_break,
                                  self.position_losscut_price) > candle.open:  # 숏 라인을 뚫고 올라올때. min을 사용하여 빠른 손절.
                if (localtime - self.position_entry_time).days >= 1:
                    quantity = self.close_short()
                    self.calc_close(localtime, candle.close, self.position_entry_price, -quantity)


if __name__ == '__main__':
    params = utils.parse_param_map(sys.argv[1:])
    year = 2018
    test_bot = Bot(None, symbol='BTCUSDT', candle_limit=24 * 7 * 2,
                   candle_period='1h',
                   test_start=f'{year}-01-01', test_end=f'{year}-12-31',
                   test_data='../candle_data/BINANCE_BTCUSDT, 60.csv',
                   # test_data='../candle_data/BITFINEX_BTCUSD, 120.csv'
                   # test_data='../candle_data/BINANCE_ETCUSDT, 60.csv',
                   # test_data='../candle_data/BITFINEX_ETHUSD, 60.csv',
                   )
    real_bot = Bot(BinanceAPI(), symbol='BTCUSDT', candle_limit=24 * 7 * 2,
                   backtest=False, candle_period='4h',
                   )

    algo = WeekBreakout(base='BTC', quote='USDT', floor_decimals=3, init_capital=1000, max_budget=1000000,
                        week_start=Yoil.MON, hour_start=0, long_rate=0.6, short_rate=0.5, buy_unit=0.01, buy_delay=1,
                        commission_rate=0.1, paper=True)

    asyncio.run(test_bot.run(algo))
    # asyncio.run(real_bot.run(algo))
