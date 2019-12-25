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

import datetime
import time
from typing import Dict, Union

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
import twitchirc

__meta_data__ = {
    'name': 'plugin_emote_limiter',
    'commands': []
}
log = main.make_log_function('emote_limiter')
emotes = {
    'monkaS': {
        'limit': 50,
        'emotes': {
            'monkaS': 1,
            'monkaW': 2,
            'monkaEXTREME': 5
        }
    },
}
channels: Dict[str, Dict[str, Union[int, float]]] = {
    # 'channel': {
    #     'limit_name': 1,  # amount left
    #     '_last_regen': time.time()  # time of last regen
    # }
}
channels_exclude = [

]
REGEN_TIME = 30
REGEN_AMOUNT = 20


def _calculate_message_cost(msg: twitchirc.ChannelMessage) -> Dict[str, int]:
    cost = {}
    for limit_name, limit_data in emotes.items():
        cost[limit_name] = 0
        for emote, emote_cost in limit_data['emotes'].items():
            cost[limit_name] += emote_cost * msg.text.count(emote)
    for k, v in cost.copy().items():
        if v == 0:
            del cost[k]
    return cost


def _check_message_cost(msg: twitchirc.ChannelMessage, cost: Dict[str, int]):
    c = channels[msg.channel]
    for limit in cost:
        # limit remaining after the message was sent
        # <=
        # 0
        if c[limit] - cost[limit] < 0:
            return False, limit, cost[limit]
    return True, None, 0


def _subtract_cost(msg: twitchirc.ChannelMessage, cost: Dict[str, int]):
    global channels
    for limit_name, limit_cost in cost.items():
        channels[msg.channel][limit_name] -= limit_cost


def _regenerate_emotes():
    curr_time = time.time()
    for ch_name, ch_data in channels.items():
        # Regenerate emotes unless the `time of last regen + time to regenerate` (time the emotes should be regenerated)
        # is bigger than the current time
        if ch_data['_last_regen'] + REGEN_TIME > curr_time:
            continue  # skip this channel
        ch_data['_last_regen'] = curr_time
        # ↓ Regenerate
        for emote_limit in ch_data.keys():
            if emote_limit == '_last_regen':
                continue
            ch_data[emote_limit] += REGEN_AMOUNT
            if ch_data[emote_limit] > emotes[emote_limit]['limit']:
                ch_data[emote_limit] = emotes[emote_limit]['limit']


def any_msg_handler(event, msg: twitchirc.Message):
    _regenerate_emotes()


def make_new_channel(name):
    channels[name] = {}
    for i in emotes:
        channels[name][i] = emotes[i]['limit']
    channels[name]['_last_regen'] = time.time()


def check_if_command_is_allowed(command_name, channel) -> bool:
    return channel in ALLOWED_CHANNELS[command_name]


def msg_handler(event, msg: twitchirc.ChannelMessage):
    if not check_if_command_is_allowed('EMOTE_LIMITER', msg.channel) or msg.text.startswith(main.bot.prefix):
        return  # Ignore commands and non active channels

    if msg.channel not in channels:
        make_new_channel(msg.channel)
    log('info', channels[msg.channel])
    cost = _calculate_message_cost(msg)
    result, limit_blocking, limit_blocking_amount = _check_message_cost(msg, cost)
    if result:
        _subtract_cost(msg, cost)
    else:
        main.bot.send(msg.reply(f'/timeout {msg.user} 1'))
        main.bot.send(msg.reply(f'@{msg.user} The channel you tried posting your message on run out of {limit_blocking}'
                                f'your message cost {limit_blocking_amount} {limit_blocking}, but you only have '
                                f'{channels[msg.channel][limit_blocking]} {limit_blocking}'))


ALLOWED_CHANNELS = {
    'emote_cost': [],
    'find_limit': [],
    'show_limits': [],
    'EMOTE_LIMITER': []
}


@main.bot.add_command('find_limit')
def command_find_limit(msg: twitchirc.ChannelMessage):
    is_allowed = check_if_command_is_allowed('find_limit', msg.channel)
    if not is_allowed:
        return
    argv = msg.text.split(' ')
    if '' in argv:
        argv.remove('')
    if len(argv) == 1:
        return (f'@{msg.user} Usage: !find_limit (emote), NOTE commands are exempt '
                f'from emote costs')
    for limit_name, limit_data in emotes.items():
        if argv[1] in limit_data['emotes']:
            return f'@{msg.user} Emote {argv[1]} belongs to limit {limit_name}.'
    return f'@{msg.user} Failed to find which limit {argv[1]} belongs to. :('


@main.bot.add_command('emote_cost')
def command_show_emote_cost(msg: twitchirc.ChannelMessage):
    is_allowed = check_if_command_is_allowed('emote_cost', msg.channel)
    if not is_allowed:
        return

    argv = msg.text.split(' ')
    if '' in argv:
        argv.remove('')
    if len(argv) == 1:
        return f'@{msg.user} Usage: !emote_cost (limit)'
    if argv[1] in emotes:
        text = []
        for k, v in emotes[argv[1]]['emotes'].items():
            text.append(f'{k} ({v})')
        return f'@{msg.user} Emotes in the {argv[1]} limit with their cost: {", ".join(text)}'
    else:
        return f'@{msg.user} {argv[1]!r}: No such emote limit.'


@main.bot.add_command('show_limits')
def command_show_limits(msg: twitchirc.ChannelMessage):
    is_allowed = check_if_command_is_allowed('show_limits', msg.channel)
    if not is_allowed:
        return

    argv = msg.text.split(' ')
    if '' in argv:
        argv.remove('')
    channel = msg.channel
    if len(argv) > 1:
        channel = argv[1]
    text = []
    if channel not in channels:
        return f"@{msg.user} Channel {channel} isn't registered in this bot or doesn't exist."
    for limit_name, limit_data in channels[channel].items():
        if limit_name == '_last_regen':
            continue
        text.append(f'{limit_data} {limit_name}')
    # datetime.datetime.now().strftime("%H:%M:%S")
    regen_time = (datetime.datetime.fromtimestamp(channels[channel]['_last_regen'] + REGEN_TIME).strftime('%Y-%m-%d '
                                                                                                          '%H:%M:%S '
                                                                                                          'CEST('
                                                                                                          'UTC+1h)'))
    return (f'@{msg.user} You have {", ".join(text)}, your limits will regenerate on '
            f'{regen_time}')


main.bot.handlers['chat_msg'].append(msg_handler)
main.bot.handlers['any_msg'].append(any_msg_handler)

if 'emote_limiter' in main.bot.storage.data:
    el_config = main.bot.storage['emote_limiter']
    if 'channels' in el_config:
        ALLOWED_CHANNELS = el_config['channels']
else:
    main.bot.storage['emote_limiter'] = {
        'channels': [

        ]
    }
