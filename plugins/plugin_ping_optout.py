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
import typing

import regex
from twitchirc import Event

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()

main.load_file('plugins/plugin_help.py')

try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'ping_optout'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)

OPTOUT_MODE_NO_AT = 0
OPTOUT_MODE_INVISIBLE_CHARACTERS = 1
OPTOUT_MODE_REPLACEMENT = 2


class Plugin(main.Plugin):
    def chan_msg_handler(self, event, msg: twitchirc.ChannelMessage):
        pass

    def __init__(self, module, source):
        super().__init__(module, source)

        self.storage = main.PluginStorage(self, main.bot.storage)

        main.bot.handlers['chat_msg'].append(self.chan_msg_handler)
        if 'ping_optouts' in self.storage:
            self.ping_optouts = self.storage['ping_optouts']
        else:
            self.ping_optouts = {}
            self.storage['ping_optouts'] = self.ping_optouts

        self.c_ping_output = main.bot.add_command('ping_optout')(self.c_ping_output)
        plugin_help.add_manual_help_using_command('Opt out from being pinged by the bot.')(self.c_ping_output)
        main.bot.middleware.append(AntiPingMiddleWare(self))

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return 'plugin_' + NAME

    @property
    def commands(self) -> typing.List[str]:
        return super().commands

    @property
    def on_reload(self):
        return super().on_reload

    @staticmethod
    def _in(obj1, obj2):
        for i in obj1:
            if i in obj2:
                return True

    def c_ping_output(self, msg: twitchirc.ChannelMessage):
        cd_state = main.do_cooldown('ping_optout', msg, global_cooldown=0, local_cooldown=30)
        if cd_state:
            return
        if msg.user in self.ping_optouts:
            del self.ping_optouts[msg.user]
            return f'@{msg.user}, you can be pinged by the bot now.'

        args = main.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 1)
        if len(args) == 1:
            return (f'@{msg.user}, please select a mode. Available modes: '
                    f'replacement (will replace ping with [PING]), '
                    f'invisibles (will add invisible characters to pings), '
                    f'no@ (will remove the @)')
        args = args[1]

        if self._in(['replace', 'replacement', 'repl', 'r'], args.lower()):
            mode = OPTOUT_MODE_REPLACEMENT
        elif self._in(['invis', 'invisibles', 'invisible', 'characters', 'i', 'chars'], args.lower()):
            mode = OPTOUT_MODE_INVISIBLE_CHARACTERS
        elif self._in(['at', 'noat', '@', 'no@', 'n@', 'no_at'], args.lower()):
            mode = OPTOUT_MODE_NO_AT
        # noinspection PyUnboundLocalVariable
        self.ping_optouts[msg.user] = mode
        return f'@{msg.user}, i will no longer ping you :)'


PING_PATTERN = regex.compile(r'@([a-zA-Z0-9_]+)')


class AntiPingMiddleWare(twitchirc.AbstractMiddleware):
    def __init__(self, parent: Plugin):
        super().__init__()
        self.parent = parent

    def send(self, event: Event) -> None:
        message = event.data['message']
        if isinstance(message, twitchirc.ChannelMessage):
            pings = PING_PATTERN.findall(message.text)
            for user in pings:
                if user.lower() in self.parent.ping_optouts:
                    mode = self.parent.ping_optouts[user.lower()]
                    if mode == OPTOUT_MODE_NO_AT:
                        message.text = message.text.replace(f'@{user}', user)
                    elif mode == OPTOUT_MODE_INVISIBLE_CHARACTERS:
                        new_ping = ''
                        for num, char in enumerate(user):
                            new_ping += char
                            if num % 3 == 0:
                                new_ping += '\U0000e000'
                        message.text = message.text.replace(f'@{user}', f'@{new_ping}')
                    elif mode == OPTOUT_MODE_REPLACEMENT:
                        message.text = message.text.replace(f'@{user}', '@[PING]')
