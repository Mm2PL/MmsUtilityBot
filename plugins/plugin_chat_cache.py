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
import json
import time
import typing
from collections import defaultdict
from typing import Dict

import regex
import requests

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc
import traceback

NAME = 'chat_cache'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    cache: Dict[str, typing.List[typing.Tuple[twitchirc.ChannelMessage, float]]]

    def __init__(self, module, source):
        super().__init__(module, source)
        # self.max_cache_length = {
        #     # 'channel': 300
        # }
        self.max_cache_length = defaultdict(lambda: 500)
        self.cache = {
            # 'channel': [
            #     # [message, time.time()]  # message, timestamp
            # ]
        }
        main.bot.handlers['chat_msg'].append(self.on_message)
        main.bot.schedule_event(0.1, 10, self._load_recents_from_connected, (), {})

    def _load_recents_from_connected(self):
        for chan in main.bot.channels_connected:
            self._load_recents(chan)

    def _load_recents(self, channel):
        log('info', f'Attempting to fetch recent messages for channel {channel}.')
        req = requests.get(f'https://recent-messages.robotty.de/api/v2/recent-messages/{channel}',
                           timeout=5)
        try:
            data = req.json()
        except json.decoder.JSONDecodeError as e:
            log('err', f'Unable to fetch recent messages for channel {channel}!\n'
                       f'{e}\n'
                       f'{traceback.format_exc()}')
            return
        if req.status_code != 200:
            log('err', f'Unable to fetch recent messages for channel {channel}!')
            log('info', repr(data))
            return
        for msg in data['messages']:
            message = twitchirc.auto_message(msg, main.bot)
            if isinstance(message, twitchirc.ChannelMessage):  # ignore messages other than normal text
                self.on_message('recent', message)

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
        pass

    def find_messages(self, channel, user=None, min_timestamp=None,
                      max_timestamp=None, expr=None) -> typing.List[twitchirc.ChannelMessage]:
        """
        Find all messages matching given criteria.

        :param channel: Channel you want to search. Required
        :param user: User you want to search for. Optional
        :param min_timestamp: Minimum timestamp to search for. Optional
        :param max_timestamp: Maximum timestamp to search for. Optional
        :param expr: Pattern you want to search for. Optional.
        :return: A list of messages found.
        """
        if expr is None:
            pattern = None
        else:
            pattern = regex.compile(expr)
        if channel in self.cache:
            ret_list = []
            for msg, t in self.cache[channel]:
                if ((user is None or msg.user == user)
                        and (pattern is None or pattern.findall(msg.text))
                        and (min_timestamp is None or min_timestamp < t)
                        and (max_timestamp is None or max_timestamp > t)):
                    ret_list.append(msg)
            return ret_list
        else:
            raise KeyError(f'Channel not found: {channel}')

    def on_message(self, event, message: twitchirc.ChannelMessage):
        self._clear_cache()
        if message.channel not in self.cache:
            self.cache[message.channel] = []
        t = None
        if 'tmi-sent-ts' in message.flags:
            t = int(message.flags['tmi-sent-ts']) / 1000
        else:
            t = time.time()
        self.cache[message.channel].append(
            (message, t)
        )

    def _clear_cache(self):
        for channel in self.cache:
            while len(self.cache[channel]) > self.max_cache_length[channel]:
                self.cache[channel].pop(0)  # delete the oldest entry.
