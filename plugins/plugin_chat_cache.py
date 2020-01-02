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
import time
import typing
from collections import defaultdict
from typing import Dict, List, Union

import regex
from twitchirc import ChannelMessage

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'chat_cache'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    cache: Dict[str, List[List[Union[ChannelMessage, float]]]]

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
        self.cache[message.channel].append(
            [message, time.time()]
        )

    def _clear_cache(self):
        for channel in self.cache:
            while len(self.cache[channel]) > self.max_cache_length[channel]:
                self.cache[channel].pop(0)  # delete the oldest entry.
