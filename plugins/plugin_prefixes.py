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
import shlex
from typing import Dict, Any

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

channel_prefixes: Dict[str, str] = {
    # 'channel': 'prefix'
}
# noinspection PyProtectedMember
old_handler = main.bot._acall_forced_prefix_commands


# noinspection PyProtectedMember
async def new_handler(message: twitchirc.ChannelMessage):
    if message.channel in channel_prefixes:
        chan_prefix = channel_prefixes[message.channel]
        if message.text.startswith(chan_prefix):
            was_handled = False
            if ' ' not in message.text:
                message.text += ' '
            for handler in main.bot.commands:
                if message.text.startswith(chan_prefix + handler.ef_command):
                    await plugin_manager._acall_handler(handler, message)
                    was_handled = True

            if not was_handled:
                main.bot._do_unknown_command(message)
        else:
            return
    else:
        await old_handler(message)


main.bot._acall_command_handlers = new_handler


def condition_prefix_exists(command: twitchirc.Command, msg: twitchirc.ChannelMessage):
    if command.forced_prefix:
        return False
    if msg.channel in channel_prefixes:
        return True


def _command_prefix_get_channel(msg: twitchirc.ChannelMessage, args: Any):
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

prefix_parser.add_argument('--channel', metavar='CHANNEL', nargs=1, dest='channel')


def _save_prefixes():
    main.bot.storage['plugin_prefixes']['prefixes'] = channel_prefixes
    # this will be saved automatically


@plugin_manager.add_conditional_alias('prefix', condition_prefix_exists)
@main.bot.add_command('mb.prefix', required_permissions=['util.prefix'], enable_local_bypass=True)
def command_prefix(msg: twitchirc.ChannelMessage):
    argv = shlex.split(msg.text.replace('\U000e0000', ''))
    args = prefix_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        return f'@{msg.user} {prefix_parser.format_usage()}'
    print(args)
    if args.query:
        args.query = ''.join(args.query)
        if args.query in channel_prefixes:
            return f'@{msg.user} Channel {args.query!r} uses prefix {channel_prefixes[args.query]}'
        elif args.query in main.bot.channels_connected:
            return f'@{msg.user} Channel {args.query!r} uses default prefix ({main.bot.prefix})'
        else:
            return f'@{msg.user} Not in channel {args.query!r}.'
    elif args.set:
        args.set = ''.join(args.set)
        temp = [i.isprintable() for i in args.set]
        rules = [len(args.set) < 4,
                 len(temp) == sum(temp)]
        del temp
        if len(rules) == sum(rules):  # prefix is valid.
            # A True value is 1, but a False is 0
            # Running sum() on the rules we can know how many rules returned True,
            # if one returned False the sum will not be equal to len() of rules.
            chan = _command_prefix_get_channel(msg, args)
            channel_prefixes[chan] = args.set
            _save_prefixes()
            return f'@{msg.user} Set prefix to {args.set!r} for channel {chan}.'
        else:
            return f'@{msg.user} Invalid prefix {args.set!r}.'


if 'plugin_prefixes' in main.bot.storage.data:
    if 'prefixes' in main.bot.storage['plugin_prefixes'] \
            and isinstance(main.bot.storage['plugin_prefixes']['prefixes'], dict):
        channel_prefixes = main.bot.storage['plugin_prefixes']['prefixes']
    else:
        main.bot.storage['plugin_prefixes']['prefixes'] = {}
        # this will be saved automatically
else:
    main.bot.storage.data['plugin_prefixes'] = {
        'prefixes': {}
    }
    main.bot.storage.save()
