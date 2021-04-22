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
import builtins
import asyncio

from plugins.utils import arg_parser

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

main.load_file('plugins/plugin_prefixes.py')

try:
    import plugin_plugin_prefixes as plugin_prefixes
except ImportError:
    import plugins.plugin_prefixes as plugin_prefixes

main.load_file('plugins/plugin_help.py')

try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

import twitchirc

__meta_data__ = {
    'name': 'plugin_debug',
    'commands': ['mb.say', 'say', 'mb.eval']
}

log = main.make_log_function('debug')


@plugin_help.add_manual_help_using_command('Say something.', aliases=['say'])
@plugin_manager.add_conditional_alias('say', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.say', required_permissions=['util.admin.say'], enable_local_bypass=False)
def command_say(msg: twitchirc.ChannelMessage):
    return msg.text.split(' ', 1)[1]


@main.bot.add_command('fsay', required_permissions=['util.admin.say.force'], enable_local_bypass=False)
def command_say(msg: twitchirc.ChannelMessage):
    return msg.reply(msg.text.split(' ', 1)[1], True)


def do_eval(code: str, msg: twitchirc.ChannelMessage):
    log('warn', f'Eval from {msg.user}({msg.flags["user-id"]}): {code!r}')
    glob = {name: getattr(builtins, name) for name in dir(builtins)}
    glob.update({
        'msg': msg, 'command_eval': command_eval,
        'log': log, 'main': main, 'plugin_help': plugin_help, 'plugin_manager': plugin_manager,
        'plugin_prefixes': plugin_prefixes
    })
    result = eval(compile(code, msg.user + '@' + msg.channel, 'eval'), glob, {})
    if isinstance(result, (list, str, twitchirc.Message)):
        return result
    else:
        return str(result)


@main.bot.add_command('mb.eval', required_permissions=['util.admin.eval'], enable_local_bypass=False)
async def command_eval(msg: twitchirc.ChannelMessage):
    assert msg.user == 'mm2pl' and msg.flags['user-id'] == '117691339', 'no.'
    code = main.delete_spammer_chrs(msg.text.split(' ', 1)[1])
    eval_result = await asyncio.get_event_loop().run_in_executor(None, do_eval, code, msg)
    return eval_result


@main.bot.add_command('mb.seval', required_permissions=['util.admin.seval', 'util.admin.eval'],
                      enable_local_bypass=False)
def command_seval(msg: twitchirc.ChannelMessage):
    assert msg.user == 'mm2pl' and msg.flags['user-id'] == '117691339', 'no.'
    code = main.delete_spammer_chrs(msg.text.split(' ', 1)[1])
    eval_result = do_eval(code, msg)
    return eval_result


@main.bot.add_command('mb.debug', required_permissions=['util.admin.debug'], enable_local_bypass=False)
async def command_debug(msg: twitchirc.ChannelMessage):
    if isinstance(msg, twitchirc.ChannelMessage):
        return f'@{msg.user}, This command is only available in whispers :)'

    argv = arg_parser.parse_args(main.delete_spammer_chrs(msg.text).rstrip(' '), {
        0: str,
        1: str
    })
    if argv[0] is ...:
        return f'debug what?'

    debugee_type = argv[0]
    print(repr(debugee_type), debugee_type == 'command', debugee_type == 'user', debugee_type == 'me',
          debugee_type in ('user', 'me'))
    if debugee_type == 'command':
        if argv[1] is ...:
            return f'debug which command?'
        cmd_name = argv[1]
        matches = list(filter(lambda c: c.chat_command == cmd_name, main.bot.commands))
        if not matches:
            fake_msg = twitchirc.ChannelMessage(cmd_name, msg.user, msg.channel, parent=main.bot)
            matches = list(filter(lambda c: c.matcher_function and c.matcher_function(fake_msg, c), main.bot.commands))
            if not matches:
                return f'Unknown command {cmd_name}'

        if len(matches) == 1:
            return _debug_command(matches[0])
        else:
            return f'@{msg.user}, {len(matches)} found.'
    elif debugee_type in ('user', 'me'):
        if argv[1] is ... and debugee_type != 'me':
            return f'@{msg.user}, how do I debug?'
        if debugee_type == 'me':
            argv[1] = msg.user

        users = main.User.get_by_name(argv[1])
        if users:
            return _debug_user(users[0])
        else:
            return f'@{msg.user}, couldn\'t find the target user.'
    else:
        return f'@{msg.user}, how to debug {debugee_type!r}?'


def _debug_command(cmd: twitchirc.Command) -> str:
    output = {
        'has_matcher': 'yes' if cmd.matcher_function else 'no', 'chat_command': repr(cmd.chat_command),
        'limit_to_channels': ('#' + ', #'.join(cmd.limit_to_channels)) if cmd.limit_to_channels else 'none',
        'available_in_whispers': 'yes' if cmd.available_in_whispers else 'no',
        'enable_local_bypass': 'yes' if cmd.enable_local_bypass else 'no',
        'forced_prefix': repr(cmd.forced_prefix), 'ef_command': repr(cmd.ef_command),
        'permissions_required': repr(cmd.permissions_required) if cmd.permissions_required else 'none',
        'no_whispers_message': ('*default*'
                                if cmd.no_whispers_message == 'This command is not available in whispers'
                                else cmd.no_whispers_message)
    }

    return ', '.join([f'{k}={v}' for k, v in output.items()])


def _debug_user(user: main.User) -> str:
    output = {
        'id': user.id,
        'twitch_id': user.twitch_id,
        'last_known_username': user.last_known_username,
        'mod_in': user.mod_in,
        'sub_in': user.sub_in
    }

    return ', '.join([f'{k}={v}' for k, v in output.items()])


@main.bot.add_command('mb.crash', required_permissions=['util.crash'], enable_local_bypass=False)
def command_generate_exception(msg: twitchirc.ChannelMessage):
    raise Exception(f'This is a test exception: {msg.text}')
