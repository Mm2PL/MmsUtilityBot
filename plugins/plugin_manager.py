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
import traceback
import typing

import twitchirc

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()

__meta_data__ = {
    'name': 'plugin_manager',
    'commands': [],
    'no_reload': True
}

log = main.make_log_function('plugin_manager')

# noinspection PyProtectedMember
call_command_handlers = main.bot._call_command_handlers

# map of command name and blacklisted channels.
blacklist: typing.Dict[
    str, typing.List[str]
] = {}
error_notification_channel = main.bot.username.lower()


def _call_handler(command, message):
    if message.channel in blacklist and command.chat_command in blacklist[message.channel]:
        # command is blocked in this channel.
        log('info', f'User {message.user} attempted to call command {command.chat_command} in channel '
                    f'{message.channel} where it is blacklisted.')
        return
    try:
        command(message)
    except Exception as e:
        msg = twitchirc.ChannelMessage(
            text=f'Errors monkaS {chr(128073)} ALERT: {e!r}',
            user='TO_BE_SENT',
            channel=error_notification_channel
        )
        msg.outgoing = True
        main.bot.force_send(msg)
        log('err', f'Error while running command {command.chat_command}')
        for i in traceback.format_exc(30).split('\n'):
            log('err', i)


# noinspection PyProtectedMember
def call_command_handlers_replacement(message: twitchirc.ChannelMessage) -> None:
    if message.text.startswith(main.bot.prefix):
        was_handled = False
        if ' ' not in message.text:
            message.text += ' '
        for handler in main.bot.commands:
            if callable(handler.matcher_function) and handler.matcher_function(message, handler):
                _call_handler(handler, message)
                was_handled = True
            if message.text.startswith(main.bot.prefix + handler.ef_command):
                _call_handler(handler, message)
                was_handled = True

        if not was_handled:
            main.bot._do_unknown_command(message)
    else:
        main.bot._call_forced_prefix_commands(message)


def add_conditional_alias(alias: str, condition: typing.Callable[[twitchirc.Command, twitchirc.ChannelMessage], bool]):
    def decorator(command: twitchirc.Command):
        @main.bot.add_command(alias, enable_local_bypass=command.enable_local_bypass,
                              required_permissions=command.permissions_required)
        def new_command(msg: twitchirc.ChannelMessage):
            if condition(command, msg):
                return command(msg)

        return command

    return decorator


@main.bot.add_command('mb.unblacklist_command', required_permissions=['util.unblacklist_command'],
                      enable_local_bypass=True)
def command_unblacklist(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    args = msg.text.split(' ')
    if len(args) != 2:
        main.bot.send(msg.reply(f'@{msg.user} Usage: '
                                f'"{main.bot.prefix}{command_unblacklist.chat_command} COMMAND". '
                                f'Where COMMAND is the command you want to unblacklist.'))
        return
    target = args[1]
    for i in main.bot.commands:
        if i.chat_command == target:
            if target not in blacklist[msg.channel]:
                main.bot.send(msg.reply(f"@{msg.user} Cannot unblacklist command {target} that isn't blacklisted "
                                        f"here."))
                return
            blacklist[msg.channel].remove(target)
            main.bot.send(msg.reply(f'@{msg.user} Unblacklisted command {target} from channel #{msg.channel}.'))
            return
    main.bot.send(msg.reply(f'@{msg.user} Cannot unblacklist nonexistent command {target}.'))


@main.bot.add_command('mb.blacklist_command', required_permissions=['util.blacklist_command'], enable_local_bypass=True)
def command_blacklist(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    args = msg.text.split(' ')
    if len(args) != 2:
        main.bot.send(msg.reply(f'@{msg.user} Usage: '
                                f'"{main.bot.prefix}{command_blacklist.chat_command} COMMAND". '
                                f'Where COMMAND is the command you want to blacklist.'))
        return
    target = args[1]
    if target in blacklist[msg.channel]:
        main.bot.send(msg.reply(f'@{msg.user} That command is already blacklisted.'))
        return

    for i in main.bot.commands:
        if i.chat_command == target:
            blacklist[msg.channel].append(target)
            main.bot.send(msg.reply(f'@{msg.user} Blacklisted command {target}. '
                                    f'To undo use {main.bot.prefix}{command_unblacklist.chat_command} {target}.'))
            return
    main.bot.send(msg.reply(f'@{msg.user} Cannot blacklist nonexistent command {target}.'))
    return


@main.bot.add_command('mb.list_blacklisted_commands', required_permissions=['util.blacklist_command'],
                      enable_local_bypass=True)
def command_list_blacklisted(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    main.bot.send(msg.reply(f'@{msg.user}, There are {len(blacklist[msg.channel])} blacklisted commands: '
                            f'{", ".join(blacklist[msg.channel])}'))


@main.bot.add_command('blacklisted_join', required_permissions=[twitchirc.PERMISSION_COMMAND_JOIN],
                      enable_local_bypass=False)
def command_join_blacklisted(msg: twitchirc.ChannelMessage) -> None:
    ensure_blacklist(msg.channel)
    chan = msg.text.split(' ')[1].lower()
    if chan in ['all']:
        main.bot.send(msg.reply(f'Cannot join #{chan}.'))
        return
    if chan in main.bot.channels_connected:
        main.bot.send(msg.reply(f'This bot is already in channel #{chan}.'))
    else:
        blacklist[msg.channel] = [i.chat_command for i in main.bot.commands]
        blacklist[msg.channel].remove('mb.blacklist_command')
        blacklist[msg.channel].remove('mb.unblacklist_command')
        blacklist[msg.channel].remove('mb.list_blacklisted_commands')
        main.bot.send(msg.reply(f'Joining channel #{chan} with all commands blacklisted apart from '
                                f'mb.blacklist_command, mb.unblacklist_command and mb.list_blacklisted_command'))
        main.bot.join(chan)


def ensure_blacklist(channel):
    if channel not in blacklist:
        blacklist[channel] = []


main.bot._call_command_handlers = call_command_handlers_replacement

if 'command_blacklist' in main.bot.storage.data:
    blacklist = main.bot.storage['command_blacklist']
else:
    main.bot.storage['command_blacklist'] = {}
