#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
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
import typing

import regex

from plugins.utils import arg_parser

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

main.load_file('plugins/plugin_chat_cache.py')
try:
    import plugin_chat_cache as plugin_chat_cache
except ImportError:
    from plugins.plugin_chat_cache import Plugin as PluginChatCache

    plugin_chat_cache: PluginChatCache

main.load_file('plugins/plugin_hastebin.py')
try:
    import plugin_hastebin as plugin_hastebin
except ImportError:
    from plugins.plugin_hastebin import Plugin as PluginHastebin

    plugin_hastebin: PluginHastebin
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'nuke'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
        'nuke'
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.c_nuke = main.bot.add_command('nuke', required_permissions=['util.nuke'],
                                           enable_local_bypass=True)(self.c_nuke)

    async def c_nuke(self, msg: twitchirc.ChannelMessage):
        try:
            args = arg_parser.parse_args(main.delete_spammer_chrs(msg.text),
                                         {
                                             'regex': str,
                                             'perma': bool,
                                             'timeout': datetime.timedelta,
                                             'search': datetime.timedelta
                                         })
        except arg_parser.ParserError as e:
            return f'@{msg.user}, error: {e.message}'
        arg_parser.check_required_keys(args, ('regex', 'timeout', 'search', 'perma'))
        if args['regex'] is ... or args['timeout'] is ... or args['search'] is ...:
            return f'@{msg.user}, regex, timeout and search are required parameters'
        if args['perma'] is ...:
            args['perma'] = False

        try:
            r = regex.compile(args['regex'])
        except Exception as e:
            return f'@{msg.user}, error while compiling regex: {e}'

        results = plugin_chat_cache.find_messages(msg.channel, expr=r,
                                                  min_timestamp=time.time() - args['search'].total_seconds())
        if not results:
            return f'@{msg.user}, found no messages matching the regex.'
        else:
            users = []
            for i in results:
                if i.user not in users:
                    users.append(i.user)
            users.remove(msg.user)  # make the executor not get hit by the fallout.
            timeouts = []
            if not args['perma']:
                t_o_length = int(args['timeout'].total_seconds())
                for u in users:
                    timeouts.append(msg.reply(f'/timeout {u} {t_o_length}s nuked.', force_slash=True))
            else:
                for u in users:
                    timeouts.append(msg.reply(f'/ban {u} nuked.', force_slash=True))

            ret = [f'@{msg.user}, {"timing out" if not args["perma"] else "banning (!!)"} {len(users)} users. '
                   f'Full list here: {plugin_hastebin.hastebin_addr}{await plugin_hastebin.upload(" ".join(users))}']
            ret.extend(timeouts)
            return ret

    @property
    def no_reload(self):
        return True

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return ['nuke']

    def on_reload(self):
        pass
