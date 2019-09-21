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
RECONNECTION_MESSAGES = [
    'WYKRYTOMIÓD RECONNECTED!',
    'HONEYDETECTED YET ANOTHER SPAM MESSAGE',
    'Look, I made Supi\'s packets come back PagChomp'
]


def chan_msg_handler(event: str, msg: twitchirc.ChannelMessage):
    if msg.user in ['supibot', 'mm2pl'] and msg.text.startswith('HONEYDETECTED RECONNECTED'):
        main.bot.send(msg.reply(random.choice(RECONNECTION_MESSAGES)))


main.bot.handlers['chat_msg'].append(chan_msg_handler)