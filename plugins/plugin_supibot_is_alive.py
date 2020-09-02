#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import asyncio
import typing

import twitchirc
from twitchirc import Event

import util_bot as main
NAME = 'supibot_is_alive'
__meta_data__ = {
    'name': NAME,
    'commands': []
}
log = main.make_log_function('supibot_is_alive')


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.stop_event = asyncio.Event()
        self.task = None
        self.middleware = SupibotMiddleware(self)
        main.bot.middleware.append(self.middleware)

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return []

    def on_reload(self):
        self.auto_kill_job()

    async def set_active(self):
        print('set active start call')
        if self.stop_event.is_set():
            print('set active exit, event set')
            return
        log('info', 'Sending Supibot active call.')
        async with (await main.supibot_api.request('PUT /bot-program/bot/active')) as r:
            if r.status == 400:
                log('err', 'Sent Supibot active call, not a bot :(, won\'t attempt again.')
                self.stop_event.set()

            elif r.status == 200:
                log('info', 'Sent Supibot active call. OK')

            elif r.status in [401, 403]:
                log('warn', 'Sent Supibot active call. Bad authorization. Won\'t attempt again.')
                self.stop_event.set()
            else:
                log('err',
                    f'Sent Supibot active call. Invalid status code: {r.status_code}, {r.content.decode("utf-8")}')

    async def pinger_task(self):
        while 1:
            await asyncio.sleep(60 * 60 * 0.5)
            await self.set_active()

    def start_pinging(self):
        self.task = asyncio.create_task(self.pinger_task())

    async def auto_kill_job(self, *args):
        print('Stopping Supibot heartbeat job.')
        self.stop_event.set()
        await self.task
        print('Done.')


class SupibotMiddleware(twitchirc.AbstractMiddleware):
    def __init__(self, parent: Plugin):
        super().__init__()
        self.parent = parent

    def aconnect(self, event: Event) -> None:
        self.parent.start_pinging()
