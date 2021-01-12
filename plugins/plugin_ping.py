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

import datetime

import psutil
# noinspection PyUnresolvedReferences
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

# ensure that plugin_prefixes is loaded.
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

__meta_data__ = {
    'name': 'plugin_ping',
    'commands': []
}
log = main.make_log_function('ping')


def _blacklist_info(channel: str):
    if plugin_manager is not None:
        plugin_manager.ensure_blacklist(channel)
        return f'{len(plugin_manager.blacklist[channel])} commands blacklisted in this channel.'
    else:
        return ''


def _channel_info():
    if main.debug:
        return f' Running on channel debug.'
    else:
        return ''


current_process = psutil.Process()


@plugin_help.add_manual_help_using_command('Show that the bot is running, how long has it been running for, '
                                           'the amount of registered commands and if possible how many commands are '
                                           'blacklisted',
                                           aliases=['ping'])
@main.bot.add_command('ping', cooldown=main.CommandCooldown(10, 5, 0))
def command_ping_simple(msg: twitchirc.ChannelMessage):
    return (f'@{msg.user} PONG! Bot has been running for '
            f'{datetime.timedelta(seconds=round(main.uptime().total_seconds()))} and is using '
            f'{current_process.memory_info().rss/1_000_000:.2f}MB of ram, '
            f'{len(main.bot.commands)} '
            f'commands registered. {_blacklist_info(msg.channel)}{_channel_info()}')
