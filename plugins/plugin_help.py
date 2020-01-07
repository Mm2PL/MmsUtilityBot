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
import argparse
import shlex
import typing
from typing import Dict, Any, Callable, Union, Tuple

import twitchirc

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    # noinspection PyUnreachableCode
    if False:
        import util_bot as main
    else:
        import main_stub
        # noinspection PyUnresolvedReferences
        import main  # load the Fake from main_stub

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

main.load_file('plugins/plugin_prefixes.py')

try:
    import plugin_plugin_prefixes as plugin_prefixes
except ImportError:
    import plugins.plugin_prefixes as plugin_prefixes

__meta_data__ = {
    'name': 'plugin_help',
    'commands': []
}
log = main.make_log_function('help')
SECTION_LINKS = 0
SECTION_COMMANDS = 1
SECTION_ARGS = 2
SECTION_MISC = 7
all_help: Dict[int, Union[Dict[str, Tuple[int, str]], Dict[str, str]]] = {
    SECTION_LINKS: {  # links
        # 'source': (1, 'target') <=> (section, target)
        'section_doc': 'Links, aliases to other topics'
    },
    SECTION_COMMANDS: {  # commands
        'section_doc': 'information about commands'
    },
    SECTION_ARGS: {  # command arguments
        'section_doc': 'information about command arguments.'
    },
    SECTION_MISC: {  # misc
        'section_doc': 'miscellaneous information, like settings.'
    }
}
MSG_LEN_LIMIT = 200


def create_topic(topic, help_, section=1, links: typing.Optional[list] = None):
    if links is not None:
        for link in links:
            all_help[0][link] = (section, topic)
    if help_ is None:
        # noinspection PyTypeChecker
        all_help[topic] = f'Topic {topic!r} exists but there was no help found :( .'
    else:
        all_help[section][topic] = help_
    log('debug', f'Created help topic {topic}({section}){f" with links {links}" if links is not None else ""}: {help_}')


def _try_find_link(topic, section: typing.Optional[int] = None) -> Union[Tuple[int, str], Tuple[None, None]]:
    if topic in all_help[0]:
        return all_help[0][topic]
    else:
        return None, None


def find_topic(topic, section: typing.Optional[int] = None) -> typing.Optional[str]:
    new_section, new_topic = None, None
    if topic not in ['section_doc']:  # don't try to find links for these topics
        new_section, new_topic = _try_find_link(topic, section)
        if section is None:
            if new_section is not None and new_topic is not None:
                section = new_section
                topic = new_topic

    if section is not None:
        if section not in all_help:
            return f'{topic}({section}) Invalid section'
        if topic in all_help[section]:
            t = all_help[section][topic]
            if isinstance(t, tuple):
                return f'{topic}({section}) Link to {t[1]}({t[0]})'
            return f'{topic}({section}) {t}'
        else:
            if new_topic is not None and new_section is not None:
                return f'{topic}({section}) Not found. However there\'s link with this name to ' \
                       f'{new_topic}({new_section})'
            return f'{topic}({section}) Not found.'
    else:
        for s, topics in all_help.items():
            log('debug', repr(s), repr(topics))
            if s == 0:  # skip links
                continue
            if topic in topics:
                log('debug', repr(topics), repr(topic), repr(s))
                return f'{topic}({s}) {topics[topic]}'
        return f'{topic}(?) Not found.'


def _help_topic_from_action(command_name, i):
    log('debug', i)
    # noinspection PyProtectedMember
    if isinstance(i, (argparse._StoreAction, argparse._AppendAction, argparse._CountAction,
                      argparse._AppendConstAction, argparse._StoreFalseAction, argparse._StoreTrueAction,
                      argparse._StoreConstAction, argparse._SubParsersAction)):
        if not i.option_strings:
            # for j in (i.dest, i.metavar, i.metavar.lower()):
            # topic = command_name + ' ' + j
            create_topic(i.dest, i.help, section=2,
                         links=[
                             command_name + ' ' + j for j in (i.dest, i.metavar.lower())
                         ])
        else:
            create_topic(i.option_strings[0],
                         i.help,
                         section=2,
                         links=[
                             command_name + ' ' + j for j in i.option_strings
                         ])


def auto_help_parser(parser: typing.Union[argparse.ArgumentParser, twitchirc.ArgumentParser],
                     aliases=None):
    # noinspection PyProtectedMember
    def decorator(command: twitchirc.Command):
        global all_help
        nonlocal aliases
        if aliases is None:
            aliases = []
        create_topic(command.chat_command,
                     (parser.format_usage().replace('\n', '')
                      + f'. See help topic \"{command.chat_command} ARGUMENT\" for explanations.'),
                     section=1,
                     links=aliases
                     )
        for i in parser._actions:
            _help_topic_from_action(command.chat_command, i)
        return command

    return decorator


def add_manual_help_using_command(help_, aliases=None):
    def decorator(command: twitchirc.Command):
        nonlocal aliases
        if aliases is None:
            aliases = []
        create_topic(command.chat_command, help_,
                     section=1,
                     links=aliases)
        return command

    return decorator


def manual_help_topics(help_: str, names: typing.List[str]):
    create_topic(names.pop(), help_, links=names)


def _command_help_meta_all(msg):
    msgs = []
    new_msg = ''
    for section, topics in all_help.items():
        for i in topics:
            if len(new_msg) + len(i) > MSG_LEN_LIMIT:
                msgs.append(new_msg)
                new_msg = ''
            else:
                new_msg += f'{i}({section}), '
    new_msg = new_msg[:-2]
    if msgs:
        return [f'@{msg.user} All help topics: ({num + 1}/{len(msgs)}) {i}' for num, i in enumerate(msgs)]
    else:
        return f'@{msg.user} All help topics: {new_msg}'


def _command_help_check_special_topics(topic, msg):
    if topic.lower() in ['all', 'topics', 'help topics', 'all topics']:
        return _command_help_meta_all(msg)
    elif topic.lower() == 'commands':
        return _command_help_meta_commands_doc(msg)
    elif topic.lower() == 'all commands':
        return _command_help_meta_commands_all(msg)


def _command_help_meta_commands_all(msg):
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
        return [f'@{msg.user} ({num + 1}/{len(msgs)}) {i}' for num, i in enumerate(msgs)]
    else:
        return f'@{msg.user} All commands: {new_msg}'


def _command_help_meta_commands_doc(msg):
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
        # for num, i in enumerate(msgs):
        #     main.bot.send(msg.reply(f'@{msg.user} All documented commands: (p{num + 1}/{len(msgs)}) {i}'))
        return [f'@{msg.user} All documented commands: ({num + 1}/{len(msgs)}) {i}' for num, i in enumerate(msgs)]
    else:
        return f'@{msg.user} All documented commands: {new_msg}'


@plugin_manager.add_conditional_alias('help', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.help')
def command_help(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('help', msg, global_cooldown=10, local_cooldown=20, )
    if cd_state:
        return

    argv = shlex.split(msg.text.replace('\U000e0000', ''))
    args: typing.List[str] = argv[1:] if len(argv) else []
    section = None
    if len(args):
        if args[0].isnumeric():
            section = int(args[0])
            args.pop(0)
    topic = ' '.join(args)
    # let the user quote the topic

    if topic == '' and section is None:  # no arguments given
        topic = 'mb.help'
    elif topic == '':  # only section given
        return f'@{msg.user} {find_topic("section_doc", section)}'

    if topic in ['all', 'topics', 'all topics', 'help topics', 'commands',
                 'all commands']:
        r = _command_help_check_special_topics(topic, msg)
        if isinstance(r, list):
            if len(r) > 3:
                return f'@{msg.user} Sorry, I can\'t send {len(r)} messages. WAYTOODANK'
            else:
                for m in r:
                    main.bot.send(msg.reply(m))
        elif r is None:
            raise RuntimeError('plugin_help._command_help_check_special_topics returned None')
    else:
        return f'@{msg.user} {find_topic(topic, section)}'


create_topic('help TOPIC', 'The topic you want to search for. It can be an existing topic or "all topics", '
                           '"commands", "all commands"',
             section=SECTION_ARGS,
             links=[
                 'mb.help TOPIC'
             ])
create_topic('help SECTION', 'The section you want to search in. See sections(7).',
             section=SECTION_ARGS,
             links=[
                 'mb.help TOPIC'
             ])
create_topic('help', 'Search for help. Man-like usage: '
                     'help SECTION TOPIC or '
                     'help TOPIC. See sections(7). Sections are denoted in parenthesis after the topic name, '
                     'like help(1)',
             section=SECTION_COMMANDS,
             links=[
                 'mb.help'
             ])
create_topic(
    'sections',
    ('Sections:'
     + ', '.join([f'{k} {v["section_doc"]}' for k, v in all_help.items()])),
    section=SECTION_MISC,
    links=[
        'help sections'
    ]
)