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
import asyncio
import typing

import discord

from util_bot import Platform
from util_bot.clients.abstract_client import AbstractClient
from util_bot.msg import StandardizedWhisperMessage, StandardizedMessage


class _Client(discord.Client):
    def __init__(self, **options):
        super().__init__(**options)
        self.message_queue = asyncio.Queue()

    async def on_message(self, message):
        if message.author == self.user:
            return

        await self.message_queue.put(message)


class DiscordClient(AbstractClient):
    def __init__(self, auth):
        super().__init__(auth)
        self.connection = _Client()
        self.connection_task = None

    async def connect(self):
        self.connection_task = asyncio.create_task(self.connection.start(self.auth))

    async def disconnect(self):
        await self.connection.logout()

    async def send(self, msg: typing.Union[StandardizedMessage, StandardizedWhisperMessage]):
        if msg.platform != Platform.DISCORD:
            return

        in_reply_to: StandardizedMessage = msg.flags['in_reply_to']
        await in_reply_to.source_message.channel.send(msg.text)

    async def receive(self):
        return convert_discord_to_standarized([await self.connection.message_queue.get()])

    async def join(self, channel):
        pass

    async def part(self, channel):
        pass

    async def flush_queues(self):
        pass


def convert_discord_to_standarized(l: typing.List[discord.Message]) \
        -> typing.List[typing.Union[StandardizedMessage,
                                    StandardizedWhisperMessage]]:
    output = []
    base_flags = {
        'badges': []
    }
    for i in l:
        if isinstance(i, discord.Message):
            flags = base_flags.copy()
            flags.update({
                'discord-user-id': i.author.id,
                'in-reply-to': None
            })
            if isinstance(i.channel, (discord.DMChannel, discord.GroupChannel)):

                new = StandardizedWhisperMessage(f'<@{i.author.id}>',
                                                 f'<@{i.channel.me.id}>',
                                                 i.content,
                                                 Platform.DISCORD,
                                                 flags,
                                                 False,
                                                 source_message=i)
            else:
                new = StandardizedMessage(i.content, f'<@{i.author.id}>', f'<#{i.channel.id}>',
                                          Platform.DISCORD, False,
                                          source_message=i)
                new.flags = flags
        else:
            new = i
        output.append(new)
    return output
