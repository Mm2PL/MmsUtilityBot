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
from urllib.parse import urlencode

import regex

try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit(1)

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit(1)
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

COOKIE_PATTERN = regex.compile(
    r'\[Cookies\] \[(Default|Bronze|Silver|Gold|Platinum|Diamond|Masters|GrandMasters|Leader)\] '
    r'([a-z0-9]+) you found a[n]? [a-zA-Z0-9]+ cookie! \(\+[0-9]+\) [a-zA-Z0-9]+? - You have [0-9]+ '
    r'cookies now! ([a-zA-Z]+?) (Use this command again in 2 hours to get another one\. 🍪)?')


class Plugin(main.Plugin):
    def chan_msg_handler(self, event: str, msg: twitchirc.ChannelMessage):
        if msg.user in ['supibot', 'mm2pl'] and msg.text.startswith('HONEYDETECTED RECONNECTED') \
                and msg.channel == 'supinic':
            random_msg = random.choice(RECONNECTION_MESSAGES)
            while '{ping}' in random_msg:
                random_msg = random_msg.replace('{ping}', random.choice(self.random_pings), 1)
            main.bot.send(msg.reply(random_msg))
        if msg.channel == 'supinic' and msg.user in ['thepositivebot', 'linkusbanned'] \
                and msg.text.startswith('\x01ACTION [Cookies]'):
            m = COOKIE_PATTERN.match(main.delete_spammer_chrs(msg.text.replace('\x01ACTION ', '')))
            if m:
                if m.group(2).lower() in self.cookie_optin:
                    main.bot.send(msg.reply(f'$remind {m.group(2)} cookie :) in 2h'))
            else:
                print('WEEEE WOOOO')
                print('WEEEE WOOOO')
                print('WEEEE WOOOO')
                print('WEEEE WOOOO')
                print('WEEEE WOOOO')
                print('WEEEE WOOOO')
                print('WEEEE WOOOO')

    def __init__(self, module, source):
        super().__init__(module, source)
        self.storage = main.PluginStorage(self, main.bot.storage)
        main.bot.handlers['chat_msg'].append(self.chan_msg_handler)
        if 'random_pings' in self.storage:
            self.random_pings = self.storage['random_pings']
        else:
            self.random_pings = ['{my pings run out}']
            self.storage['random_pings'] = self.random_pings

        if 'pyramid_enabled' in self.storage:
            self.pyramid_enabled = self.storage['pyramid_enabled']
        else:
            self.pyramid_enabled = []
            self.storage['pyramid_enabled'] = self.pyramid_enabled

        if 'cookie_optin' in self.storage:
            self.cookie_optin = self.storage['cookie_optin']
        else:
            self.cookie_optin = []
            self.storage['cookie_optin'] = self.cookie_optin

        # register commands
        self.command_pyramid = main.bot.add_command('mb.pyramid', required_permissions=['cancer.pyramid'],
                                                    enable_local_bypass=True)(self.c_pyramid)
        plugin_help.add_manual_help_using_command('Make a pyramid.', None)(self.command_pyramid)

        self.command_braillefy = main.bot.add_command('braillefy')(self.c_braillefy)
        plugin_help.add_manual_help_using_command('Convert an image into braille.', None)(self.command_braillefy)

        self.c_cookie_optin = main.bot.add_command('cookie')(self.c_cookie_optin)
        plugin_help.add_manual_help_using_command('Add yourself to the list of people who will be reminded to eat '
                                                  'cookies', None)(self.c_cookie_optin)

    def c_cookie_optin(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('cookie', msg, global_cooldown=60, local_cooldown=60)
        if cd_state:
            return
        if msg.user.lower() in self.cookie_optin:
            self.cookie_optin.remove(msg.user.lower())
            return f'@{msg.user} You have been removed from the cookie opt-in list.'
        else:
            self.cookie_optin.append(msg.user.lower())
            return f'@{msg.user} You have been added to the cookie opt-in list.'

    def c_pyramid(self, msg: twitchirc.ChannelMessage):
        if msg.channel not in self.pyramid_enabled:
            return f'@{msg.user}, This command is disabled here.'
        cd_state = main.do_cooldown('pyramid', msg, global_cooldown=60, local_cooldown=60)
        if cd_state:
            return
        t = main.delete_spammer_chrs(msg.text).split(' ', 1)
        if len(t) == 1:
            return f'@{msg.user}, Usage: pyramid <text...>'
        args = t[1].rstrip()
        size = ''
        for i in args.split(' '):
            i: str
            if i.isnumeric():
                size = i
        if size != '':
            args = args.replace(size, '', 1).rstrip() + ' '
            size = int(size)
            print(repr(args), repr(size))
            for i in range(1, size):
                main.bot.send(msg.reply(args * i))
            for i in range(size, 0, -1):
                main.bot.send(msg.reply(args * i))

    # noinspection PyUnreachableCode
    def c_braillefy(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('braille', global_cooldown=0, local_cooldown=60, msg=msg)
        if cd_state:
            return
        return f'@{msg.user} this command isn\'t finished yet.'
        _next_token = 'url'
        url = None

        options = {
            'reverse': False,
            'size_percent': None,
            'max_x': None,
            'max_y': None,
            'sensitivity': (1.0, 1.0, 1.0, 1.0)
        }
        for num, part in enumerate(main.delete_spammer_chrs(msg.text).split(' ')):
            part: str
            if _next_token == 'url':
                _next_token = 'option'
                url = part
            elif _next_token == 'option':
                opt = part.split(':', 1)
                if len(opt) == 1:
                    return f'@{msg.user} No value provided for option {opt} at position {num}'

        main.bot.send(f'@{msg.user}'
                      f'http://kotmisia.pl/api/ascii/{url}'
                      f'?{"&".join([f"{urlencode(k)}={urlencode(v)}" for k, v in options])}')
