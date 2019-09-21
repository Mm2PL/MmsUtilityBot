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
import typing
from typing import List

import requests

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

try:
    import plugin_plugin_prefixes as plugin_prefixes
except ImportError:
    import plugins.plugin_prefixes as plugin_prefixes

import twitch_auth

__meta_data__ = {
    'name': 'plugin_whois',
    'commands': [
        'whois'
    ]
}
log = main.make_log_function('whois')
whois_requests: List[typing.Dict[str, typing.Union[str, requests.Request, twitchirc.ChannelMessage]]] = []

whois_parser = twitchirc.ArgumentParser(prog='whois')
g = whois_parser.add_mutually_exclusive_group(required=True)
g.add_argument('-i', '--id', help='Use the ID instead of using a username', dest='id', type=int)
g.add_argument('-n', '--name', help='Use the username', dest='name', type=str)


@plugin_manager.add_conditional_alias('whois', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.whois')
def command_whois(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('whois', msg, global_cooldown=30,
                                local_cooldown=60)
    if cd_state:
        return
    argv = shlex.split(msg.text.replace('\U000e0000', ''))
    args = whois_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        main.bot.send(msg.reply(f'@{msg.user} {whois_parser.format_usage()}'))
        return
    params = {

    }
    if args.id is not None:
        params['id'] = args.id
    if args.name is not None:
        params['login'] = args.name

    r = requests.get('https://api.twitch.tv/helix/users', params=params,
                     headers={'Client-ID': twitch_auth.json_data['client_id']})

    # whois_requests.append({
    #     'msg': msg,
    #     'request': r
    # })
    def _handle_request():
        data = r.json()
        if data['data']:
            data = data['data']
            user = data[0]
            main.bot.send(msg.reply(f'@{msg.user} User {user["display_name"]}, '
                                    f'ID: {user["id"]}, login: {user["login"]}, '
                                    f'User type: '
                                    f'{user["broadcaster_type"] + "," if user["broadcaster_type"] else "normal user"} '
                                    f'{", " + user["type"] if user["type"] else "with normal permissions"}. '
                                    f'Description: {user["description"]}'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} No such user found.'))
        main.bot.flush_queue(10) 

    main.bot.schedule_event(1, 10, _handle_request, (), {})
