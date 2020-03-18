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
import inspect
import json
import time
import typing
import warnings
from typing import Set

import websockets


class PubsubWarning(UserWarning):
    pass


class PubsubClient:
    topics: Set[str]

    def __init__(self, token, ping_time=15):
        self.ping_time = ping_time
        self.open_lock = asyncio.Lock()
        self.token = token

        self.callbacks = {

        }
        self.is_connected = False
        self.initialized = False
        self.socket = None
        self.send_queue = asyncio.Queue()
        self.task = None

        self.topics = set()

    async def initialize(self):
        self.task = asyncio.get_event_loop().create_task(self._run())
        return self.task

    def send(self, data):
        self.send_queue.put_nowait(data)

    def listen(self, topics: typing.Iterable[str]):
        print('listen', topics)
        for i in topics:
            if i not in self.callbacks:
                self.callbacks[i] = []
        self.topics.update(topics)
        self.send(
            {
                'type': 'LISTEN',
                'nonce': '',
                'data': {
                    'topics': topics,
                    'auth_token': self.token
                }
            }
        )

    def unlisten(self, topics):
        for topic in topics:
            del self.callbacks[topic]
        self.topics.difference(topics)
        self.send(
            {
                'type': 'UNLISTEN',
                'nonce': '',
                'data': {
                    'topics': topics
                }
            }
        )

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                self.task = None
                return
            else:
                raise RuntimeError('Task didn\'t raise CanceledError, while canceling background pubsub task.')
        else:
            raise RuntimeError('Attempted to cancel a task that does\'t exist, while canceling background pubsub task.')

    def register_callback(self, topic: str) -> typing.Callable[[typing.Callable], typing.Callable]:
        """
        Register a callback for the provided topic.

        This method is a decorator
        """
        if topic not in self.callbacks:
            self.callbacks[topic] = []

        def decorator(func: typing.Callable) -> typing.Callable:
            self.callbacks[topic].append(func)
            return func

        return decorator

    async def _sender(self, queue, ws):
        while 1:
            try:
                elem = await queue.get()

                print(f'> {elem}')
                await ws.send(json.dumps(elem))
            except asyncio.CancelledError:
                break

    async def _pinger(self, queue: asyncio.Queue):
        while 1:
            try:
                await asyncio.sleep(self.ping_time)
                await queue.put({
                    'type': 'PING'
                })
            except asyncio.CancelledError:
                break

    async def _run(self):
        while 1:
            last_pong = time.time() + 20
            async with websockets.connect('wss://pubsub-edge.twitch.tv') as ws:
                print('Connected to pubsub')
                sender_task = asyncio.create_task(self._sender(self.send_queue, ws))
                pinger_task = asyncio.create_task(self._pinger(self.send_queue))
                while 1:
                    try:
                        recved_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        # haven't received anything for 5 seconds, check if a PONG should have came in.
                        if last_pong + self.ping_time * 2 < time.time():
                            # no pong in last 30 seconds, this means either we aren't sending PINGs
                            # or the connection is dead, reconnect
                            break
                        continue

                    print(f'< {recved_msg!r}')
                    msg = json.loads(recved_msg)
                    if msg['type'] == 'MESSAGE':
                        topic = msg['data']['topic']
                        data = json.loads(msg['data']['message'])

                        for f in self.callbacks[topic]:
                            if inspect.iscoroutinefunction(f):
                                await f(topic, data)
                            else:
                                f(topic, data)
                        else:
                            warnings.warn(f'UNHANDLED PUBSUB MESSAGE TOPIC {topic}', PubsubWarning)
                    elif msg['type'] == 'RESPONSE':
                        if msg['error']:
                            warnings.warn(f'PUBSUB ERROR {msg["error"]}', PubsubWarning)
                    elif msg['type'] == 'PONG':
                        if last_pong + self.ping_time * 2 < time.time():
                            # print('reconnect')
                            break  # late pong, possible connections issues, better to just reconnect.
                        last_pong = time.time()
                        # print('cancel reconnect')
                    elif msg['type'] == 'RECONNECT':
                        break
                    else:
                        warnings.warn(f'UNHANDLED PUBSUB MESSAGE TYPE {msg["type"]!r}, msg => {msg}', PubsubWarning)
                sender_task.cancel()
                await sender_task
                pinger_task.cancel()
                await pinger_task
                await ws.close()
