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
import asyncio
import builtins

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
