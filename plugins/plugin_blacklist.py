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
import queue
import threading
import time
import typing
from typing import List

import regex
from twitchirc import Event

from plugins.utils import arg_parser

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit()
# noinspection PyUnresolvedReferences
import twitchirc
import plugins.models.blacklistentry as blacklistentry_model

NAME = 'blacklist'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)
expire_queue = queue.Queue()
blacklists: List['BlacklistEntry'] = []
BlacklistEntry = blacklistentry_model.get(main.Base, main.session_scope, blacklists, expire_queue)
TIMEDELTA_REGEX = regex.compile(r'(\d+d(?:ays)?)?([0-5]?\dh(?:ours?)?)?([0-5]?\dm(?:inutes?)?)?'
                                r'([0-5]?\ds(?:econds?)?)?')


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.expire_lock = threading.Lock()
        main.bot.schedule_event(0.1, 10, self._post_init, (), {})
        self.expire_thread = threading.Thread(target=self._periodically_expire, args=(), kwargs={}, daemon=True)
        self.expire_thread.start()
        main.reloadables['blacklist'] = self.reload_blacklist
        decorator = main.bot.add_command('plonk', enable_local_bypass=False, required_permissions=['blacklist.plonk'])
        self.command_manage_blacklists = decorator(self.command_manage_blacklists)
        del decorator

        decorator = plugin_help.add_manual_help_using_command('Manage blacklists. '
                                                              'Usage: plonk [scope:(channel|global)] '
                                                              '(user:(user|everyone)) '
                                                              '(command:(command_name|all)) '
                                                              '[expires:(never|timedelta)]')
        decorator(self.command_manage_blacklists)

    def reload_blacklist(self):
        global blacklists
        with self.expire_lock:  # don't expire black lists while reloading
            blacklists.clear()
            with main.session_scope() as dank_circle:
                blacklists.extend(BlacklistEntry.load_all(dank_circle))

    def _post_init(self):
        global blacklists
        # load all entries
        with main.session_scope() as dank_circle:
            blacklists.clear()
            blacklists.extend(BlacklistEntry.load_all(dank_circle))

        # initialize middleware
        main.bot.middleware.append(
            BlacklistMiddleware()
        )

    def _periodically_expire(self):
        while 1:
            time.sleep(30)  # don't need to flush this right away.
            to_expire = []
            while 1:
                try:
                    o = expire_queue.get_nowait()
                    to_expire.append(o)
                except queue.Empty:
                    break
            if to_expire:
                with main.session_scope() as session, self.expire_lock:
                    for e in to_expire:
                        e: BlacklistEntry
                        session.delete(e)

    def command_manage_blacklists(self, msg: twitchirc.ChannelMessage):
        argv = main.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 1)
        if len(argv) == 1:
            return f'@{msg.user}, {plugin_help.all_help[plugin_help.SECTION_COMMANDS]["plonk"]}'
        text = argv[1]
        try:
            kw = arg_parser.parse_args(
                text,
                {
                    'scope': str,
                    'user': str,
                    'command': str,
                    'expires': datetime.timedelta
                },
                defaults={
                    'scope': None,
                    'user': None,
                    'command': None,
                    'expires': None
                }
            )
        except arg_parser.ParserError as e:
            return e.message

        if kw['command'] is None:
            return f'@{msg.user}, No `command:...` provided.'
        if kw['user'] is None:
            return f'@{msg.user}, No `user:...` provided.'

        kw['user'] = kw['user'].lower()
        if kw['user'] == 'everyone':
            kw['user'] = True

        kw['scope'] = kw['scope'].lower().strip('#')
        if kw['scope'] != 'global':
            sc = []
            for ch in kw['scope'].split(','):
                ch = ch.lstrip('#').lower()
                if ch not in main.bot.channels_connected:
                    return f'@{msg.user}, Invalid `scope`: {kw["scope"]!r}, no such channel.'
                sc.append(ch)
            kw['scope'] = sc
        if kw['command'].lower() == 'all':
            kw['command'] = True
        else:
            cmd = None
            for i in main.bot.commands:
                i: main.Command
                if i.chat_command.lower() == kw['command'] or kw['command'] in i.aliases:
                    cmd = i.chat_command
            if cmd is None:
                return f'@{msg.user}, Invalid `command`: {kw["command"]!r}. No such command exists.'
            else:
                kw['command'] = cmd
            del cmd

        if kw['expires']:
            kw['expires'] = datetime.datetime.now() + kw['expires']

        with main.session_scope() as session:
            if kw['scope'] == 'global':
                targets = main.User.get_by_name(kw['user'], session) if kw['user'] is not True else None

                if targets is None or len(targets) == 1:
                    obj = BlacklistEntry(target=targets[0] if targets is not None else targets,
                                         command=kw['command'] if kw['command'] is not True else None,
                                         channel=None, expires_on=kw['expires'],
                                         is_active=True)
                    blacklists.append(obj)
                    session.add(obj)
                elif len(targets) == 0:
                    return f'@{msg.user} Failed to find user: {kw["user"]}'
                else:
                    return f'@{msg.user} Found multiple users possible with name {kw["user"]}'
            else:
                for ch in kw['scope']:
                    targets = main.User.get_by_name(kw['user'], session) if kw['user'] is not True else None
                    channels = main.User.get_by_name(ch, session)
                    if len(channels) == 1:
                        if targets is None or len(targets) == 1:
                            obj = BlacklistEntry(target=targets[0] if targets is not None else targets,
                                                 command=kw['command'] if kw['command'] is not True else None,
                                                 channel=channels[0],
                                                 expires_on=kw['expires'],
                                                 is_active=True)
                            blacklists.append(obj)
                            session.add(obj)
                        elif len(targets) == 0:
                            return f'@{msg.user} Failed to find user: {kw["user"]}'
                        else:
                            return f'@{msg.user} Found multiple users possible with name {kw["user"]}'
                    elif len(channels) == 0:
                        return f'@{msg.user} Failed to find channel: {ch}'
                    elif len(channels) > 1:
                        return f'@{msg.user} Found multiple channels possible with name {ch}'
        return f'@{msg.user}, Added blacklist for command {kw["command"]} with scope {kw["scope"]} for {kw["user"]}'

    @property
    def no_reload(self):
        return True

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return super().commands

    @property
    def on_reload(self):
        return super().on_reload


class BlacklistMiddleware(twitchirc.AbstractMiddleware):
    def command(self, event: Event) -> None:
        if event.canceled:
            return
        message: twitchirc.ChannelMessage = event.data['message']
        command: twitchirc.Command = event.data['command']
        for bl in blacklists:
            r = bl.check(message, command)
            if r is True:
                log('info', f'Ignored {message.user}\'s command ({command.chat_command!r}) '
                            f'because of blacklist {bl.id}, message: {message.text}')
                event.cancel()
