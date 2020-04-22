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
from typing import Dict
import typing

import twitchirc
from twitchirc import Event

from apis.pubsub import PubsubClient
import util_bot

channel_live_state: Dict[str, bool] = {
    # 'channel': False
}


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
        pubsub.unlisten([
            f'video-playback.{channel}'
        ])

    def live_handler(self, topic: str, msg: dict):
        channel_name = topic.replace('video-playback.', '')
        if channel_name not in channel_live_state:
            channel_live_state[channel_name] = False

        print(msg)
        if msg['type'] in ['stream-up', 'viewcount']:
            if not channel_live_state[channel_name]:
                util_bot.bot.call_middleware('stream-up', (channel_name,), False)
            channel_live_state[channel_name] = True
        elif msg['type'] == 'stream-down':
            if channel_live_state[channel_name]:
                util_bot.bot.call_middleware('stream-down', (channel_name,), False)
            channel_live_state[channel_name] = False

    async def restart_pubsub(self):
        await pubsub.stop()
        await pubsub.initialize()

    def connect(self, event: Event) -> None:
        asyncio.get_event_loop().create_task(
            self.restart_pubsub()
        )

    def on_action(self, event: Event):
        super().on_action(event)


pubsub: typing.Optional[PubsubClient] = None


async def init_pubsub(token):
    global pubsub
    pubsub = PubsubClient(token)
    await pubsub.initialize()
    return pubsub
