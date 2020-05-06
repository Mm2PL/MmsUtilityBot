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
import shlex
from typing import Any

from util_bot import Platform
from util_bot.msg import StandardizedMessage, StandardizedWhisperMessage

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager

    raise ImportError("Cannot load the plugin_manager. Let's crash :)")

# noinspection PyUnresolvedReferences
import twitchirc

__meta_data__ = {
    'name': 'plugin_prefixes',
    'commands': []
}
log = main.make_log_function('prefixes')


# noinspection PyProtectedMember

def condition_prefix_exists(command: twitchirc.Command, msg: StandardizedMessage):
    if command.forced_prefix:
        return False
    if (msg.channel, msg.platform) in main.bot.prefixes:
        return True
    if msg.platform in main.bot.prefixes and isinstance(msg, StandardizedWhisperMessage):
        return True


def _command_prefix_get_channel(msg: StandardizedMessage, args: Any):
    if main.bot.check_permissions(msg, ['util.prefix.set_other'], enable_local_bypass=False):
        # user doesn't have the permissions needed to the a prefix for another channel, ignore --channel
        return msg.channel
    else:
        if args.channel is not None:
            args.channel = ''.join(args.channel)
            return args.channel
        else:
            return msg.channel


prefix_parser = twitchirc.ArgumentParser(prog='mb.prefix')
g = prefix_parser.add_mutually_exclusive_group(required=True)
g.add_argument('--query', metavar='CHANNEL', nargs=1, help='Check the prefix set on channel CHANNEL.',
               dest='query')
g.add_argument('--set', metavar='NEW_PREFIX', nargs=1, help='Set the prefix on the current channel '
                                                            '(can be overridden by --channel) to '
                                                            'NEW_PREFIX. This action cannot be undone '
                                                            'using the old prefix, be careful',
               dest='set')
g.add_argument('--set-platform',
               metavar=('NEW_PREFIX', 'PLATFORM'),
               nargs=2,
               help='Set the prefix on the current platform '
                    'to NEW_PREFIX. This action cannot be undone '
                    'using the old prefix, be careful',
               dest='set_platform')

prefix_parser.add_argument('--channel', metavar='CHANNEL', nargs=1, dest='channel')


@plugin_manager.add_conditional_alias('prefix', condition_prefix_exists)
@main.bot.add_command('mb.prefix', required_permissions=['util.prefix'], enable_local_bypass=True)
async def command_prefix(msg: StandardizedMessage):
    argv = shlex.split(msg.text.replace('\U000e0000', ''))
    args = prefix_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        return f'@{msg.user} {prefix_parser.format_usage()}'
    print(args)
    if args.query:
        args.query = ''.join(args.query)
        ident = (args.query, msg.platform)
        if ident in main.bot.prefixes:
            return f'@{msg.user} Channel {args.query!r} uses prefix {main.bot.prefixes[ident]}'
        elif args.query in main.bot.channels_connected:
            return f'@{msg.user} Channel {args.query!r} uses default prefix ({main.bot.prefix})'
        else:
            return f'@{msg.user} Not in channel {args.query!r}.'
    elif args.set:
        args.set = ''.join(args.set)
        temp = [i.isprintable() for i in args.set]
        rules = [len(args.set) < 4,
                 all(temp)]
        del temp
        if all(rules):  # prefix is valid.
            chan = _command_prefix_get_channel(msg, args)
            main.bot.prefixes[(chan, msg.platform)] = args.set

            return (f'@{msg.user} Set prefix to {args.set!r} for channel {chan} on platform'
                    f' {msg.platform.name.capitalize()!r}.')
        else:
            return f'@{msg.user} Invalid prefix {args.set!r}.'
    elif args.set_platform:
        args.set_platform, plat = args.set_platform

        try:
            plat = Platform[plat.upper()]
        except IndexError:
            return f'@{msg.user}, invalid platform: {plat.upper()!r}'

        temp = [i.isprintable() for i in args.set_platform]
        rules = [len(args.set_platform) < 4,
                 all(temp)]
        del temp
        if all(rules):
            missing_perms = main.bot.check_permissions(msg, ['util.prefix.set_platform'], enable_local_bypass=False)
            if missing_perms:
                return (f'@{msg.user}, You are missing permissions to change the bot prefix for the whole platform '
                        f'({msg.platform.name.capitalize()})')
            main.bot.prefixes[plat] = args.set_platform
            return (f'@{msg.user} Set prefix to {args.set_platform!r} for platform'
                    f' {plat.name.capitalize()}.')
        else:
            return f'@{msg.user} Invalid prefix {args.set_platform!r}.'
