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

# this file allows for managing simple commands without manually changing the config.
import argparse
import shlex
import typing
from dataclasses import dataclass
import datetime
from typing import Dict

import json5

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()
import twitchirc

__meta_data__ = {
    'name': 'plugin_simple_command_manager',
    'commands': []
}

log = main.make_log_function('simple_command_manager')

add_echo_command_parser = twitchirc.ArgumentParser(prog='mb.add_echo_command')
add_echo_command_parser.add_argument('name', metavar='NAME', help='Name of the command')
add_echo_command_parser.add_argument('-s', '--scope', metavar='SCOPE', help='Channels this commands will run in. '
                                                                            'You need special permissions to have it '
                                                                            'run in '
                                                                            'channels you don\'t own',
                                     default='!!LOCAL')
add_echo_command_parser.add_argument('data', metavar='TEXT', nargs=argparse.REMAINDER, help='Text to be returned.')


@main.bot.add_command('mb.add_echo_command', required_permissions=['util.add_command'],
                      enable_local_bypass=True)
def add_echo_command(msg: twitchirc.ChannelMessage):
    argv = shlex.split(msg.text.replace('\U000e0000', ''))
    args = add_echo_command_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        main.bot.send(msg.reply(f'@{msg.user} {add_echo_command_parser.format_usage()}'))
        return
    print(args)
    if args.scope == '!!LOCAL':
        scope = [msg.channel]
    else:
        scope = args.scope.split(',')
        for i in scope:
            if i not in main.bot.channels_connected:
                main.bot.send(msg.reply(f'@{msg.user} Cannot add command: bot isn\'t in channel #{i}.'))
                return

            missing_permissions = main.bot.check_permissions(msg, ['util.add_command.non_local'],
                                                             enable_local_bypass=False)
            if i != msg.user and not missing_permissions:
                main.bot.send(msg.reply(f'@{msg.user} You don\'t have permissions to create a command with this scope.'
                                        f'Offending entry: {i!r}. If you still want to do it create a local command '
                                        f'and use "mb.enable_command {args.name}" to enable it there '
                                        f'(mod rights are required).'))
                return

    for j in main.bot.commands:
        if j.chat_command == args.name:
            # todo: make this ignore commands disabled in the `scope`
            main.bot.send(msg.reply(f'@{msg.user} Cannot add command: command already exists.'))
            return

    text = ' '.join(args.data)
    main.new_echo_command(args.name,
                          text,
                          limit_to_channel=scope,
                          command_source='commands.json')

    with open('commands.json', 'r') as file:
        data: typing.List[typing.Dict[str, typing.Union[typing.List[str], str]]] = json5.load(file)
    data.append(
        {
            'name': args.name,
            'message': text,
            'channel': scope,
            'type': 'echo'
        }
    )
    with open('commands.json', 'w') as file:
        json5.dump(data, file, indent=4, sort_keys=True)

    main.bot.send(msg.reply(f'@{msg.user} Added echo command {args.name!r} with message {text!r} in channels '
                            f'{scope!r}'))


@dataclass
class Deletion:
    user: str
    command_to_delete: str
    expiration_time: datetime.datetime


delete_list: Dict[str, Deletion] = {
    # 'user': Deletion()
}


def _delete_custom_command(cmd: twitchirc.Command) -> bool:
    with open('commands.json', 'r') as file:
        data: typing.List[typing.Dict[str, typing.Union[typing.List[str], str]]] = json5.load(file)
    was_deleted = False
    for i, j in enumerate(data.copy()):
        if j['name'] == cmd.chat_command:
            was_deleted = True
            del data[i]
    if was_deleted:
        with open('commands.json', 'w') as file:
            json5.dump(data, file, indent=4, sort_keys=True)
        return True
    return False


def _delete_command(command_to_delete, channel, is_global=False) -> typing.Tuple[int, str]:
    if command_to_delete in [i.chat_command for i in main.bot.commands]:
        cmd = main.bot.commands[command_to_delete]
        if is_global:
            main.bot.remove(cmd)
            if hasattr(cmd, 'source'):
                _delete_custom_command(cmd)
            return 0, ''
        elif channel in cmd.limit_to_channels:
            cmd.limit_to_channels.remove(channel)
            # noinspection PySimplifyBooleanCheck
            if cmd.limit_to_channels == []:
                # this can be None, don't fall for not cmd.limit_to_channels.
                main.bot.commands.remove(cmd)
            return 0, ''
        else:
            return 1, f'Command {command_to_delete} isn\'t active in channel {channel}'
    else:
        return 1, f"Command {command_to_delete} doesn't exist."


delete_command_parser = twitchirc.ArgumentParser(prog='mb.delete_command')
delete_command_parser.add_argument('--global', help='Delete the command globally, not only in this channel.',
                                   dest='is_global')

g2 = delete_command_parser.add_mutually_exclusive_group()
g2.add_argument('--delete', metavar='TARGET', help='Command to delete.')

g2.add_argument('--confirm-delete', metavar='COMMAND', help='Confirm deletion of command COMMAND.',
                dest='confirm')


@main.bot.add_command('mb.delete_command')
def delete_command(msg: twitchirc.ChannelMessage):
    argv = shlex.split(msg.text.replace('\U000e0000', ''))
    args = delete_command_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        main.bot.send(msg.reply(f'@{msg.user} {delete_command_parser.format_usage()}'))
        return

    if args.confirm:
        if msg.user in delete_list:
            del delete_list[msg.user]
            delete_action = delete_list[msg.user]
            if delete_action.expiration_time < datetime.datetime.now():
                main.bot.send(msg.reply(f'@{msg.user} Your request has expired.'))
                return
            if delete_action.command_to_delete != args.confirm:
                main.bot.send(msg.reply(f'@{msg.user} Cannot confirm deletion of command '
                                        f'{delete_action.command_to_delete!r}. You typed {args.confirm!r}.'))
                return 1
            else:
                exit_code, message = _delete_command(delete_action.command_to_delete, msg.channel, args.is_global)
                if exit_code != 0:
                    main.bot.send(msg.reply(f'@{msg.user} Failed to delete command: {message}'))
                else:
                    main.bot.send(msg.reply(f'@{msg.user} Deleted command {delete_action.command_to_delete!r}'
                                            f'successfully.'))
                return
        else:
            main.bot.send(msg.reply(f'@{msg.user} You don\'t have an action to confirm.'))
    else:
        if args.target in [i.chat_command for i in main.bot.commands]:
            cmd = None
            for i in main.bot.commands:
                if i.chat_command == args.target and not args.is_global and (i.limit_to_channels is not None and
                                                                             msg.channel in i.limit_to_channels):
                    cmd = i
            if cmd is None:
                main.bot.send(msg.reply(f'@{msg.user} Command {args.target!r} doesn\'t exist in this scope.'))
                return
            delete_list[msg.user] = Deletion(
                msg.user, args.target, datetime.datetime.now() + datetime.timedelta(seconds=30)
            )
            scope = 'in the global scope.' if args.is_global else f'in the scope of this channel (#{msg.channel})'
            main.bot.send(msg.reply(f'@{msg.user} Confirm you want to delete command {args.target!r} in '
                                    f'{scope} using (prefix)mb.delete_command --confirm-delete COMMAND_NAME.'
                                    f'You have 30 seconds to do this.'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} Command {args.target} doesn\'t exist.'))
