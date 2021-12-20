#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
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

import abc
import typing

import util_bot


class AbstractClient(abc.ABC):
    def __init__(self, auth):
        self.auth = auth

    @abc.abstractmethod
    async def connect(self):
        pass

    @abc.abstractmethod
    async def disconnect(self):
        pass

    @abc.abstractmethod
    async def send(self, msg):
        pass

    @abc.abstractmethod
    async def receive(self):
        pass

    @abc.abstractmethod
    async def join(self, channel):
        pass

    @abc.abstractmethod
    async def part(self, channel):
        pass

    @abc.abstractmethod
    async def flush_queues(self):
        pass

    @abc.abstractmethod
    async def format_mention(self, msg) -> str:
        pass

    async def reconnect(self):
        await self.disconnect()
        await self.connect()

    @abc.abstractmethod
    def channel_ident(
            self,
            msg  # type: typing.Union[util_bot.StandardizedWhisperMessage, util_bot.StandardizedMessage]
    ) -> str:
        ...
