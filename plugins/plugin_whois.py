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
import atexit
import datetime
import queue
import shlex
import threading

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

__meta_data__ = {
    'name': 'plugin_whois',
    'commands': [
        'whois'
    ]
}
log = main.make_log_function('whois')
# whois_requests: List[typing.Dict[str, typing.Union[str, requests.Request, twitchirc.ChannelMessage]]] = []
message_return_queue = queue.Queue()
request_queue = queue.Queue()

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
    try:
        argv = shlex.split(msg.text.replace('\U000e0000', ''))
    except ValueError as e:
        main.bot.send(msg.reply(f'@{msg.user} FeelsWeirdMan {e.args}'))
        return

    args = whois_parser.parse_args(argv[1:] if len(argv) > 1 else [])
    if args is None:
        main.bot.send(msg.reply(f'@{msg.user} {whois_parser.format_usage()}'))
        return
    if args.id is not None:
        name = args.id
        id_ = True
    elif args.name is not None:
        name = args.name
        id_ = False
    else:
        main.bot.send(msg.reply(f'@{msg.user} Do you really want the bot to crash?'))
        return

    r = requests.get(f'https://api.ivr.fi/twitch/resolve/{name}',
                     params=({'id': 1}) if id_ else {},
                     headers={
                         'User-Agent': 'Mm\'sUtilityBot/v1.0 (by Mm2PL), Twitch chat bot',
                         'Requested-By': msg.user
                     })
    request_queue.put_nowait((r, msg))


def _request_handler(in_queue: queue.Queue, out_queue: queue.Queue):
    while 1:
        task, msg = in_queue.get()
        task: requests.Request
        msg: twitchirc.ChannelMessage
        if isinstance(task, bool):
            return task
        data = task.json()
        if data['status'] == 404:
            out_queue.put(msg.reply(f'@{msg.user} No such user found.'))
            continue
        roles = 'none'
        if data['roles']['isAffiliate']:
            roles = 'affiliate, '
        if data['roles']['isPartner']:
            roles += 'partner, '
        if data['roles']['isSiteAdmin']:
            roles += 'site admin, '
        if data['roles']['isStaff']:
            roles += 'staff'

        roles = (roles[::-1].replace(', '[::-1], '', 1))[::-1]
        # replace last ", " with "".
        if data['displayName'].lower() != data['login'].lower():
            login = f'({data["login"]})'
        else:
            login = ''
        created_on = datetime.datetime.strptime(data['createdAt'][:-8], '%Y-%m-%dT%H:%M:%S')
        out_queue.put(msg.reply(f'@{msg.user}, {"BANNED " if data["banned"] else ""}{"bot " if data["bot"] else ""}'
                                f'user {data["displayName"]}{login}, '
                                f'chat color: {data["chatColor"]}, '
                                f'account created at {created_on}, roles: {roles}, bio: '
                                f'{data["bio"] if data["bio"] is not None else "not set"}'))


thread = threading.Thread(target=_request_handler, args=(request_queue, message_return_queue))
thread.start()


@atexit.register
def _thread_stopper(*args, **kwargs):
    del args, kwargs
    request_queue.put((True, None))


def _message_sender():
    try:
        elem = message_return_queue.get_nowait()
    except queue.Empty:
        return
    if isinstance(elem, twitchirc.ChannelMessage):
        main.bot.send(elem)
        main.bot.flush_queue(10)


main.bot.schedule_repeated_event(0.1, 10, _message_sender, (), {})
