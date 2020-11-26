#  This is a simple utility util_bot.bot
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
import time
from typing import Dict
import typing

import twitchirc
from twitchirc import Event

from apis.pubsub import PubsubClient
import util_bot

CHANNEL_VIEW_COUNT_TIMEOUT = 60
CHANNEL_STREAM_UP_TIMEOUT = 120
channel_live_state: Dict[str, typing.Union[float, None]] = {
    # 'channel': False
}
listened_channels = set()


class PubsubMiddleware(twitchirc.AbstractMiddleware):
    def join(self, event: Event) -> None:
        channel: str = event.data['channel']
        topic: str = f'video-playback.{channel}'
        print(f'join channel {channel}')
        pubsub.listen([
            topic
        ])
        pubsub.register_callback(topic)(self.live_handler)

    def part(self, event: Event) -> None:
        channel: str = event.data['channel']
        topic = f'video-playback.{channel}'
        pubsub.unlisten([
            topic
        ])

    def _clean_up_cache(self):
        now = time.monotonic()
        to_delete = set()
        for k, v in channel_live_state.items():
            if v is None or v < now:
                to_delete.add(k)

        for key in to_delete:
            del channel_live_state[key]

    async def live_handler(self, topic: str, msg: dict):
        self._clean_up_cache()
        channel_name = topic.replace('video-playback.', '')
        if channel_name not in channel_live_state:
            channel_live_state[channel_name] = time.monotonic()

        if msg['type'] == 'viewcount':
            if not channel_live_state.get(channel_name):
                await util_bot.bot.acall_middleware('stream-up', {
                    'channel_name': channel_name,
                    'message': msg,
                    'topic': topic
                }, False)

            await util_bot.bot.acall_middleware('viewcount', {
                'channel_name': channel_name,
                'message': msg,
                'topic': topic
            }, False)
            channel_live_state[channel_name] = time.monotonic() + CHANNEL_VIEW_COUNT_TIMEOUT
        elif msg['type'] == 'stream-up':
            if not channel_live_state.get(channel_name):
                await util_bot.bot.acall_middleware('stream-up', {
                    'channel_name': channel_name,
                    'message': msg,
                    'topic': topic
                }, False)
            channel_live_state[channel_name] = time.monotonic() + CHANNEL_STREAM_UP_TIMEOUT
        elif msg['type'] == 'stream-down':
            if channel_live_state.get(channel_name):
                await util_bot.bot.acall_middleware('stream-down', {
                    'channel_name': channel_name,
                    'message': msg,
                    'topic': topic
                }, False)
            del channel_live_state[channel_name]
        else:
            await util_bot.bot.acall_middleware('unknown_pubsub_stream_event', {
                'channel_name': channel_name,
                'message': msg,
                'topic': topic
            }, False)

    async def restart_pubsub(self):
        await pubsub.stop()
        await pubsub.initialize()

    def connect(self, event: Event) -> None:
        asyncio.get_event_loop().create_task(
            self.restart_pubsub()
        )
        for chan in util_bot.bot.clients[util_bot.Platform.TWITCH].connection.channels_connected:
            self.join(chan)

    def on_action(self, event: Event):
        super().on_action(event)

    async def aon_action(self, event: Event):
        if event.name == 'join':
            self.join(event)
        elif event.name == 'part':
            self.part(event)


pubsub: typing.Optional[PubsubClient] = None


async def init_pubsub(token):
    global pubsub
    pubsub = PubsubClient(token)
    await pubsub.initialize()
    return pubsub
