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
import asyncio
import typing
from typing import List

import pydle

import util_bot
from .abstract_client import AbstractClient
# noinspection PyUnresolvedReferences
from ..msg import StandardizedMessage, StandardizedWhisperMessage
# noinspection PyUnresolvedReferences
from ..platform import Platform

_BaseIrc = pydle.featurize(pydle.features.IRCv3_1Support)

NETWORK_ID_KEY = 'internal-network-id'


def convert_irc_to_standardized(
        l: typing.List[typing.Dict[str, str]],
        message_parent,
        network_id
) -> typing.List[typing.Union[StandardizedMessage, StandardizedWhisperMessage]]:
    output = []
    for i in l:
        if i['type'] == 'privmsg':
            if i['target'].startswith('#'):
                msg = StandardizedMessage(
                    text=i['message'],
                    user=i['by'],
                    channel=i['target'].replace('#', '', 1),
                    platform=Platform.IRC,
                    outgoing=False,
                    parent=message_parent,
                    source_message=i,
                )
            else:
                msg = StandardizedWhisperMessage(
                    text=i['message'],
                    user_from=i['by'],
                    user_to=i['target'].lstrip('@'),
                    platform=Platform.IRC,
                    outgoing=False,
                    source_message=i,
                )
            msg.flags[NETWORK_ID_KEY] = network_id
            output.append(msg)
    return output


class _Irc(_BaseIrc):
    __connected_futures: List[asyncio.Future]

    def __init__(self, *args, network_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.channels_connected = []
        self.encoding = 'utf-8'
        self.__connected_futures = []
        self.queue = asyncio.Queue()
        self.id_ = network_id

    # async def on_connect(self):
    async def on_raw_nick(self, *args):
        await super().on_raw_nick(*args)
        print(f'#{self.id_} is NICKED!!')
        # for i in self.channels_connected:
        #     await self.join('#' + i)
        # print(f'#{self.id_} is JOINED!!')
        print('resolve futures')
        for i in self.__connected_futures:
            i.set_result(None)
        self.__connected_futures.clear()
        print(f'#{self.id_} is RESOLVED!!')
        print('resolved futures')

    async def on_join(self, channel, user):
        await super().on_join(channel, user)

    async def on_channel_message(self, target, by, message):
        await super().on_channel_message(target, by, message)
        await self.queue.put(
            convert_irc_to_standardized(
                [
                    {
                        'type': 'privmsg',
                        'target': target,
                        'by': by,
                        'message': message
                    },
                ],
                message_parent=self,
                network_id=self.id_
            )
        )

    async def on_raw(self, message):
        print(str(message).replace('\n', '').replace('\r', ''))
        return await super().on_raw(message)

    async def join(self, channel):
        print(f'#{self.id_} Join channel {channel!r} start')
        await super().join(channel)
        print(f'#{self.id_} Join channel {channel!r} FINISH!')

    def until_ready(self):
        if self.registered:
            f = asyncio.Future()
            f.set_result(None)
            return f
        fut = asyncio.Future()
        self.__connected_futures.append(fut)
        return fut


class IrcClient(AbstractClient):
    platform = Platform.IRC

    networks: List[_Irc]
    network_hosts: List[dict]

    async def format_mention(self, msg) -> str:
        return msg.user

    def __init__(self, opts):
        assert isinstance(opts, list)
        super().__init__(opts)
        self.networks = []
        self.network_hosts = []

        for network in opts:
            host = network['host']
            auth = network['auth']
            self.networks.append(_Irc(network_id=len(self.networks), **auth))
            self.network_hosts.append(host)

    async def connect(self):
        for i, network in enumerate(self.networks):
            await network.connect(**self.network_hosts[i])
        for network in self.networks:
            print(f'Waiting until network #{network.id_} ({self.network_hosts[network.id_]!r}) is ready...')
            await network.until_ready()
            print(f'#{network.id_} is done...')

    async def disconnect(self):
        for network in self.networks:
            await network.connection.disconnect()

    def _network_id_from_msg(self, msg):
        in_reply_to = msg.flags.get('in_reply_to')
        default = in_reply_to.flags[NETWORK_ID_KEY] if in_reply_to else None
        network_id: typing.Optional[int] = msg.flags.get(NETWORK_ID_KEY, default)
        return network_id

    async def send(self, msg):
        network_id = self._network_id_from_msg(msg)
        if network_id is None:
            raise ValueError('Unable to send message without a network ID.')

        if isinstance(msg, StandardizedMessage):
            print(await self.networks[network_id].message('#' + msg.channel, msg.text))
        elif isinstance(msg, StandardizedWhisperMessage):
            print(await self.networks[network_id].message(msg.user_to, msg.text))
        else:
            raise RuntimeError(f'IrcClient doesn\'t know how to send {msg!r} as a message.')

    async def receive(self):
        done, _ = await asyncio.wait([i.queue.get() for i in self.networks], return_when=asyncio.FIRST_COMPLETED)
        return await done.pop()

    async def join(self, channel):
        if ':' in channel:
            network_id, channel = channel.split(':', 1)
            await self.networks[int(network_id)].join(channel)
        else:
            raise ValueError('Needs network_id:#channel_name.')

    async def part(self, channel):
        if ':' in channel:
            network_id, channel = channel.split(':', 1)
            await self.networks[int(network_id)].part(channel)
        else:
            raise ValueError('Needs network_id:#channel_name.')

    async def flush_queues(self):
        ...  # this client doesn't require this call

    def channel_ident(self,
                      msg: typing.Union[util_bot.StandardizedWhisperMessage, util_bot.StandardizedMessage]) -> str:
        assert msg.platform == self.platform, 'what the fuck?'
        network_id = self._network_id_from_msg(msg)
        if network_id is None:
            raise ValueError('channel_ident called on a message which does not have any network identification')
        return f'irc:{network_id}:#{msg.channel}'
