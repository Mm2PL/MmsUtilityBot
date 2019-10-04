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
import argparse
import shlex
import typing
from typing import Dict, Any, Callable

import twitchirc

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

try:
    import plugin_plugin_prefixes as plugin_prefixes
except ImportError:
    import plugins.plugin_prefixes as plugin_prefixes

__meta_data__ = {
    'name': 'plugin_help',
    'commands': []
}
log = main.make_log_function('help')
all_help = {

}
MSG_LEN_LIMIT = 200


def _create_topic(topic, help_):
    if help_ is None:
        all_help[topic] = f'Topic {topic!r} exists but there was no help found :( .'
    else:
        all_help[topic] = help_
    print(f'Created help topic {topic}')


def _help_topic_from_action(command_name, i):
    print(i)
    # noinspection PyProtectedMember
    if isinstance(i, (argparse._StoreAction, argparse._AppendAction, argparse._CountAction,
                      argparse._AppendConstAction, argparse._StoreFalseAction, argparse._StoreTrueAction,
                      argparse._StoreConstAction, argparse._SubParsersAction)):
        if not i.option_strings:
            for j in [i.dest, i.metavar]:
                topic = command_name + ' ' + j
                _create_topic(topic, i.help)
        for j in i.option_strings:
            topic = command_name + ' ' + j
            _create_topic(topic, i.help)


def auto_help_parser(parser: typing.Union[argparse.ArgumentParser, twitchirc.ArgumentParser],
                     aliases=None):
    # noinspection PyProtectedMember
    def decorator(command: twitchirc.Command):
        nonlocal aliases
        if aliases is None:
            aliases = []
        aliases.append(command.chat_command)
        for command_name in aliases:
            all_help[command_name] = (parser.format_usage().replace('\n', '')
                                      + f'. See help topic \"{command_name} ARGUMENT\" for explanations.')
            for i in parser._actions:
                _help_topic_from_action(command_name, i)
        return command

    return decorator


def add_manual_help_using_command(help_, aliases=None):
    def decorator(command: twitchirc.Command):
        nonlocal aliases
        if aliases is None:
            aliases = []
        aliases.append(command.chat_command)
        for i in aliases:
            _create_topic(i, help_)
        return command

    return decorator


def manual_help_topics(help_, names):
    for i in names:
        _create_topic(i, help_)


command_help_parser = twitchirc.ArgumentParser(prog='help')
command_help_parser.add_argument('topic', metavar='TOPIC', help='The topic you want to search for.',
                                 nargs='+')


@plugin_manager.add_conditional_alias('help', plugin_prefixes.condition_prefix_exists)
@auto_help_parser(command_help_parser, ['help'])
@main.bot.add_command('mb.help')
def command_help(msg: twitchirc.ChannelMessage):
    argv = shlex.split(msg.text.replace('\U000e0000', ''))
    args = command_help_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        main.bot.send(msg.reply(f'@{msg.user} {command_help_parser.format_usage()}'))
        return

    topic = ' '.join(args.topic).replace('\"', '').replace("\'", '')
    # let the user quote the topic
    print(repr(topic))
    if topic.lower() in ['all', 'topics', 'help topics']:
        msgs = []
        new_msg = ''
        for i in all_help.keys():
            if len(new_msg) + len(i) > MSG_LEN_LIMIT:
                msgs.append(new_msg)
                new_msg = ''
            else:
                new_msg += i + ', '
        new_msg = new_msg[:-2]
        if msgs:
            for num, i in enumerate(msgs):
                main.bot.send(msg.reply(f'@{msg.user} ({num + 1}/{len(msgs)}) {i}'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} All help topics: {new_msg}'))
    elif topic.lower() == 'commands':
        all_commands: Dict[str, Callable[..., Any]] = {}
        for command in main.bot.commands:
            if command.chat_command not in all_help:
                continue
            if command.function in all_commands.values():
                continue
            else:
                if command.limit_to_channels is not None and msg.channel in command.limit_to_channels:
                    all_commands[command.chat_command] = command.function
                elif command.limit_to_channels is None:
                    all_commands[command.chat_command] = command.function
        msgs = []
        new_msg = ''
        for i in all_commands.keys():
            if len(new_msg) + len(i) > MSG_LEN_LIMIT:
                msgs.append(new_msg)
                new_msg = ''
            else:
                new_msg += i + ', '
        new_msg = new_msg[:-2]
        if msgs:
            for num, i in enumerate(msgs):
                main.bot.send(msg.reply(f'@{msg.user} All documented commands: (p{num + 1}/{len(msgs)}) {i}'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} All documented commands: {new_msg}'))

    elif topic.lower() == 'all commands':
        all_commands: Dict[str, Callable[..., Any]] = {}
        for command in main.bot.commands:
            if command.function in all_commands.values():
                continue
            else:
                if command.limit_to_channels is not None and msg.channel in command.limit_to_channels:
                    all_commands[command.chat_command] = command.function
                elif command.limit_to_channels is None:
                    all_commands[command.chat_command] = command.function
        msgs = []
        new_msg = ''
        for i in all_commands.keys():
            if len(new_msg) + len(i) > MSG_LEN_LIMIT:
                msgs.append(new_msg)
                new_msg = ''
            else:
                new_msg += i + ', '
        new_msg = new_msg[:-2]
        if msgs:
            for num, i in enumerate(msgs):
                main.bot.send(msg.reply(f'@{msg.user} ({num + 1}/{len(msgs)}) {i}'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} All commands: {new_msg}'))
    elif topic not in all_help:
        main.bot.send(msg.reply(f'@{msg.user} No such topic found'))
    else:
        main.bot.send(msg.reply(f'@{msg.user} {topic!r}: {all_help[topic]}'))
