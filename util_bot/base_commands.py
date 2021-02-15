#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
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

import twitchirc

import util_bot
from . import Platform
from .msg import StandardizedMessage


# region perm command

async def command_perm(msg: StandardizedMessage):
    p = twitchirc.ArgumentParser(prog='!perm', add_help=False)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('-a', '--add', metavar=('USER', 'PERMISSION'), nargs=2, dest='add')
    g.add_argument('-r', '--remove', metavar=('USER', 'PERMISSION'), nargs=2, dest='remove')
    g.add_argument('-l', '--list', metavar='USER', const=msg.user, default=None, nargs='?', dest='list')
    g.add_argument('-f', '--flush', action='store_true', dest='flush')
    g.add_argument('-h', '--help', action='store_true', dest='help')

    p.add_argument('-c', '--command', action='store_true', dest='update_for_command')
    args = p.parse_args(args=msg.text.split(' ')[1:])
    if args is None or args.help:
        usage = f'@{msg.user} {p.format_usage()}'
        return usage
    if args.update_for_command:
        cmd_name = (args.add and args.add[1]) or (args.remove and args.remove[1])
        cmd: typing.Optional[util_bot.Command] = None
        for command in util_bot.bot.commands:
            if command.chat_command == cmd_name or cmd_name in command.aliases:
                cmd = command
                break
        if cmd:
            args.add = args.add and (args.add[0], ','.join(cmd.permissions_required))
            args.remove = args.remove and (args.remove[0], ','.join(cmd.permissions_required))
        else:
            return f'@{msg.user}, {cmd_name!r}: command not found.'

    if args.add:
        return await _perm_add(args, msg)
    elif args.remove:
        return await _perm_remove(args, msg)
    elif args.list:
        return await _perm_list(args, msg)
    elif args.flush:
        return await _perm_flush(args, msg)


async def _perm_flush(args, msg):
    util_bot.bot.permissions.fix()
    for i in util_bot.bot.permissions:
        util_bot.bot.storage['permissions'][i] = util_bot.bot.permissions[i]
    util_bot.bot.storage.save()
    return f'@{msg.user}, Flushed permissions.'


async def _perm_list(args, msg):
    if await util_bot.bot.acheck_permissions(msg, [twitchirc.PERMISSION_COMMAND_PERM_LIST]):
        return (f"@{msg.user} You cannot use !perm -l, since you don't have"
                f"the {twitchirc.PERMISSION_COMMAND_PERM_LIST} permission")
    args.list = args.list.lower()

    if args.list not in util_bot.bot.permissions:
        util_bot.bot.permissions[args.list] = []

    output = ', '.join(util_bot.bot.permissions[args.list])
    if output:
        return f'User {args.list} has permissions: {output}'
    else:
        return f'User {args.list} does\'t have any permissions.'


async def _perm_remove(args, msg):
    if await util_bot.bot.acheck_permissions(msg, [twitchirc.PERMISSION_COMMAND_PERM_REMOVE],
                                             enable_local_bypass=False):
        return (f"@{msg.user} You cannot use !perm -r, since you don't have"
                f"the {twitchirc.PERMISSION_COMMAND_PERM_REMOVE} permission")

    if args.remove[0] not in util_bot.bot.permissions:
        util_bot.bot.permissions[args.remove[0]] = []

    if args.remove[1] not in util_bot.bot.permissions[args.remove[0]]:
        return (f"@{msg.user} User {args.remove[0]} already "
                f"doesn't have permission {args.remove[1]}.")
    else:
        util_bot.bot.permissions[args.remove[0]].remove(args.remove[1])
        return f'@{msg.user} Removed permission {args.remove[1]} from user {args.remove[0]}.'


async def _perm_add(args, msg):
    if await util_bot.bot.acheck_permissions(msg, [twitchirc.PERMISSION_COMMAND_PERM_ADD], enable_local_bypass=False):
        return (f"@{msg.user} You cannot use !perm -a, since you don't have"
                f"the {twitchirc.PERMISSION_COMMAND_PERM_ADD} permission")
    if args.add[0] not in util_bot.bot.permissions:
        util_bot.bot.permissions[args.add[0]] = []

    if args.add[1] not in util_bot.bot.permissions[args.add[0]]:
        util_bot.bot.permissions[args.add[0]].append(args.add[1])

        return f'@{msg.user} Given permission {args.add[1]} to user {args.add[0]}.'
    else:
        return f'@{msg.user} User {args.add[0]} already has permission {args.add[1]}.'


# endregion
async def command_part(msg: StandardizedMessage):
    if msg.platform != Platform.TWITCH:
        return f'@{msg.user}, This command only works on Twitch.'

    p = twitchirc.ArgumentParser(prog=msg.text.split(' ', 1)[0], add_help=False)
    p.add_argument('channel', metavar='CHANNEL', nargs='?', const=msg.channel, default=msg.channel)
    p.add_argument('-h', '--help', action='store_true', dest='help')
    args = p.parse_args(msg.text.split(' ')[1:])
    if args is None or args.help:
        usage = f'@{msg.user} {p.format_usage()}'
        return usage
    if args.channel == '':
        args.channel = msg.channel
    channel = args.channel.lower()
    missing_perms = await util_bot.bot.acheck_permissions(msg, [twitchirc.PERMISSION_COMMAND_PART_OTHER],
                                                          enable_local_bypass=False)

    if channel != msg.channel.lower() and missing_perms:
        return (f'Cannot part from channel #{channel}: you don\'t have permissions to run this command from anywhere, '
                f'run it in that channel to prove that you have at least moderator permissions there.')
    if channel not in util_bot.bot.channels_connected:
        return f'Not in #{channel}'
    else:
        await util_bot.bot.part(channel)

        li = util_bot.bot.storage['channels']
        while channel in li:
            li.remove(channel)
        util_bot.bot.storage.save()

        return f'Parted from #{channel}'


async def command_join(msg: StandardizedMessage):
    if msg.platform != Platform.TWITCH:
        return f'@{msg.user}, This command only works on Twitch.'

    chan = msg.text.split(' ')[1].lower()
    if chan in ['all']:
        return f'@{msg.user}, Cannot join #{chan}.'

    if chan in util_bot.bot.channels_connected:
        return f'@{msg.user}, The bot is already in channel #{chan}.'
    else:
        await util_bot.bot.join(chan)
        util_bot.bot.storage['channels'].append(chan)
        util_bot.bot.storage.save()

        return f'@{msg.user}, Joined channel #{chan}.'
