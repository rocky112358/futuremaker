import asyncio
import os
import threading
import time
from collections import deque
from datetime import datetime

import pytz
import requests

from futuremaker import nexus_mock
from futuremaker import utils
from futuremaker.log import logger
from futuremaker.nexus import Nexus


class Bot(object):
    """
    봇.
    """

    def __init__(self, api, symbol, candle_limit=20, candle_period='1h',
                 backtest=True, paper=True, timezone='Asia/Seoul', test_start=None, test_end=None, test_data=None):

        if not symbol:
            raise Exception('Symbol must be set.')
        if not candle_period:
            raise Exception('candle_period must be set. 1m, 5m,..')

        self.messages = deque()
        self.api = api
        self.symbol = symbol
        self.candle_period = candle_period
        self.backtest = backtest
        self.paper = paper
        self.timezone = timezone
        self.local_tz = pytz.timezone(timezone)
        self.telegram_bot_token = os.getenv('bot_token')
        self.telegram_chat_id = os.getenv('chat_id')

        if not self.backtest:
            self.nexus = Nexus(api, symbol, candle_limit=candle_limit, candle_period=candle_period)
        else:
            self.nexus = nexus_mock.Nexus(candle_limit, test_start, test_end, test_data)

    def start_sched(self):
        loop = asyncio.new_event_loop()
        # print('Thread Event Loop > ', loop)
        loop.run_until_complete(self.sched())

    async def sched(self):
        while True:
            try:
                while self.messages:
                    item = self.messages.popleft()
                    await self.__send_telegram(item)
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(1)
            except:
                utils.print_traceback()

    def send_message(self, text):
        if not self.backtest:
            self.messages.append(text)

    async def __send_telegram(self, text):
        if self.telegram_bot_token and self.telegram_chat_id:
            return await utils.send_telegram(self.telegram_bot_token, self.telegram_chat_id, text)
        else:
            logger.warn('BotToken 과 ChatId 가 설정되어 있지 않아 텔레그램 메시지를 보내지 않습니다.')

    async def run(self, algo):
        self.nexus.callback(update_candle=algo._update_candle)

        algo.api = self.api
        algo.local_tz = self.local_tz
        algo.send_message = self.send_message
        algo.backtest = self.backtest
        try:
            logger.info('SYMBOL: %s', self.symbol)
            logger.info('CANDLE_PERIOD: %s', self.candle_period)
            logger.info('UCT: %s', datetime.utcnow())
            logger.info('ENV[TZ]: %s', os.getenv("TZ"))
            logger.info('TIMEZONE: %s', self.timezone)
            logger.info('LocalTime: %s', utils.localtime(datetime.utcnow(), self.local_tz))
            logger.info('LOGLEVEL: %s', os.getenv("LOGLEVEL"))
            logger.info('TZNAME: %s', time.tzname)
            ip_address = requests.get('https://api.ipify.org?format=json').json()['ip']
            logger.info('IP: %s', ip_address)
            self.send_message(f'{algo.get_name()} Bot started.. {ip_address}')
            logger.info('Loading...')

            # 봇 상태로드
            algo.load_status()
            # ready 구현체가 있다면 호출.
            algo.ready()

            if not self.backtest:
                t = threading.Thread(target=self.start_sched,  daemon=True)
                t.start()
            await self.nexus.load()
            logger.info('Start!')
            await self.nexus.start()
        except KeyboardInterrupt:
            pass
