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

# noinspection PyUnresolvedReferences
import twitchirc
import datetime

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


@plugin_manager.add_conditional_alias('ping', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.ping')
def command_ping_simple(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('ping', msg, global_cooldown=int(1.5 * 60), local_cooldown=2 * 60)
    if cd_state:
        return
    main.bot.send(msg.reply(f'@{msg.user} PONG! Bot has been running for '
                            f'{datetime.timedelta(seconds=round(main.uptime().total_seconds()))}. '
                            f'{len(main.bot.commands)} '
                            f'commands registered. {_blacklist_info(msg.channel)}'))
