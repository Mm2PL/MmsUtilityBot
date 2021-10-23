#  This is a simple utility bot
#  Copyright (C) 2021 Mm2PL
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
import typing

import prometheus_client as prom
import twitchirc
from twitchirc import Event

import util_bot

NAME = 'prometheus'
__meta_data__ = {
    'name': NAME,
    'commands': []
}
log = util_bot.make_log_function(NAME)


class Plugin(util_bot.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.middleware = None

    @property
    def port(self):
        return util_bot.bot.storage.data.get('prometheus_port', 9093)

    async def async_init(self):
        self._setup_prom_data()
        prom.start_http_server(self.port, 'localhost')

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return super().commands

    @property
    def on_reload(self):
        return super().on_reload

    def _setup_prom_data(self):
        self.middleware = PromScrapeMiddleware(self)
        util_bot.bot.middleware.append(self.middleware)
        self.messages_sent = prom.Counter(
            'messages_sent',
            'Messages sent by channel',
            ['channel']
        )
        self.messages_received = prom.Counter(
            'messages_received',
            'Messages received by channel',
            ['channel']
        )
        self.commands_executed = prom.Counter(
            'commands_executed',
            'Commands executed by name',
            ['command']
        )
        self.hastebins_created = prom.Counter(
            'hastebins_created',
            'Hastebins created'
        )


class PromScrapeMiddleware(twitchirc.AbstractMiddleware):
    def __init__(self, parent: Plugin):
        super().__init__()
        self.parent = parent

    async def send(self, event: Event) -> None:
        msg: util_bot.StandardizedMessage = event.data.get('message')
        self.parent.messages_sent.labels(msg.channel).inc()

    async def receive(self, event: Event) -> None:
        msg: util_bot.StandardizedMessage = event.data.get('message')
        if isinstance(msg, util_bot.StandardizedMessage):
            self.parent.messages_received.labels(msg.channel).inc()

    async def command(self, event: Event) -> None:
        if event.canceled:
            return
        cmd: util_bot.Command = event.data['command']
        self.parent.commands_executed.labels(cmd.chat_command).inc()

    async def aon_action(self, event: Event):
        if event.name == 'send':
            await self.send(event)
        elif event.name == 'receive':
            await self.receive(event)
        elif event.name == 'command':
            await self.command(event)
