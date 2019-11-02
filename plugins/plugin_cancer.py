#  This is a simple utility bot
#  Copyright (C) 2019 Maciej Marciniak
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

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()
import random

import twitchirc

__meta_data__ = {
    'name': 'plugin_cancer',
    'commands': []
}

log = main.make_log_function('cancerous_plugin')
with open(__file__, 'r') as f:
    lines = f.readlines()
    file_lines = len(lines)
    file_length = sum([len(i) for i in lines])

del lines

RECONNECTION_MESSAGES = [
    'WYKRYTOMIÓD RECONNECTED!',
    'HONEYDETECTED YET ANOTHER SPAM MESSAGE',
    'Look, I made Supi\'s packets come back PagChomp',
    'asd',
    f'Look, this cancerous "feature" is only {file_length} characters',
    f'Look, this cancerous "feature" is only {file_lines} lines',
    'FeelsGoodMan Clap spam',
    '🅱ing @{ping} PepeS'
]


# random_pings = main.bot.storage.

class Plugin(main.Plugin):
    def chan_msg_handler(self, event: str, msg: twitchirc.ChannelMessage):
        if msg.user in ['supibot', 'mm2pl'] and msg.text.startswith('HONEYDETECTED RECONNECTED'):
            random_msg = random.choice(RECONNECTION_MESSAGES)
            while '{ping}' in random_msg:
                random_msg = random_msg.replace('{ping}', random.choice(self.random_pings), 1)
            main.bot.send(msg.reply(random_msg))

    def __init__(self, module, source):
        super().__init__(module, source)
        self.storage = main.PluginStorage(self, main.bot.storage)
        main.bot.handlers['chat_msg'].append(self.chan_msg_handler)
        if 'random_pings' in self.storage:
            self.random_pings = self.storage['random_pings']
        else:
            self.random_pings = ['{my pings run out}']
            self.storage['random_pings'] = self.random_pings
