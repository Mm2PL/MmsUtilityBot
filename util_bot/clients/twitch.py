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
import ssl
import typing

import twitchirc
from twitchirc import Event

from util_bot.clients.abstract_client import AbstractClient
from util_bot.msg import StandardizedMessage, StandardizedWhisperMessage
from util_bot.platform import Platform
from util_bot.utils import watch, Reconnect
import util_bot


class TwitchClient(AbstractClient):
    platform = Platform.TWITCH

    def __init__(self, auth):
        super().__init__(auth)
        self.connection = twitchirc.Connection('irc.chat.twitch.tv', 6697, secure=True)
        self.middleware = EventPassingMiddleware(util_bot.bot)
        self.connection.middleware.append(self.middleware)

    async def connect(self):
        self.connection.connect(*self.auth)
        self.connection.cap_reqs(False)
        if self.connection.channels_connected:
            channels = self.connection.channels_connected.copy()
            self.connection.channels_connected.clear()
            for i in channels:
                await self.join(i)

    async def disconnect(self):
        try:
            self.connection.disconnect()
        except ssl.SSLZeroReturnError as e:
            return  # connection is dead eShrug

    async def send(self, msg):
        try:
            self.connection.send(msg)
        except ssl.SSLZeroReturnError as e:
            raise Reconnect(self.platform) from e

    async def receive(self):
        await watch(self.connection.socket.fileno())

        try:
            should_reconnect = self.connection.receive() == 'RECONNECT'
        except (ConnectionResetError, BrokenPipeError) as e:
            raise Reconnect(self.platform) from e

        if should_reconnect:
            raise Reconnect(self.platform)
        return convert_twitchirc_to_standarized(self.connection.process_messages(1000, mode=-1), self.connection)

    async def join(self, channel):
        self.connection.join(channel)

    async def part(self, channel):
        self.connection.part(channel)

    async def flush_queues(self):
        self.connection.flush_queue(100)

    async def reconnect(self):
        self.connection.call_middleware('reconnect', (), False)
        await self.disconnect()
        util_bot.twitch_auth.refresh()
        util_bot.twitch_auth.save()
        self.auth = (self.auth[0], 'oauth:' + util_bot.twitch_auth.json_data['access_token'])
        await self.connect()


def convert_twitchirc_to_standarized(l: typing.List[typing.Union[twitchirc.ChannelMessage, twitchirc.WhisperMessage,
                                                                 twitchirc.Message]],
                                     message_parent) -> \
        typing.List[typing.Union[StandardizedMessage, StandardizedWhisperMessage]]:
    output = []
    for i in l:
        if isinstance(i, twitchirc.ChannelMessage):
            new = StandardizedMessage(i.text, i.user, i.channel, Platform.TWITCH, False, parent=message_parent)
            new.flags = i.flags
        elif isinstance(i, twitchirc.WhisperMessage):
            new = StandardizedWhisperMessage(i.user_from, i.user_to, i.text, Platform.TWITCH, i.flags, False)
        else:
            new = i
        output.append(new)
    return output


class EventPassingMiddleware(twitchirc.AbstractMiddleware):
    def __init__(self, target):
        self.target: util_bot.Bot = target
        self.accepted_events = ['disconnect', 'reconnect']

    def on_action(self, event: Event):
        if event not in self.accepted_events:
            return
        # noinspection PyProtectedMember
        self.target.call_middleware(event.name, event.data, event._cancelable)
