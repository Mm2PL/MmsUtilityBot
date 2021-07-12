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
import time
import typing

import aiohttp
# noinspection PyUnresolvedReferences
import twitchirc

import util_bot.constants

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

try:
    import plugin_plugin_prefixes as plugin_prefixes
except ImportError:
    import plugins.plugin_prefixes as plugin_prefixes

try:
    import plugin_hastebin as plugin_hastebin
except ImportError:
    from plugins.plugin_hastebin import Plugin as _PluginHastebin

    plugin_hastebin: _PluginHastebin
    raise

import plugins.utils.arg_parser as arg_parser

__meta_data__ = {
    'name': 'plugin_whois',
    'commands': [
        'whois'
    ]
}
log = util_bot.make_log_function('whois')


@util_bot.bot.add_command('mb.whois')
async def command_whois(msg: util_bot.StandardizedMessage):
    if not bots or bots_invalidates <= time.time():
        await _load_bots()

    cd_state = util_bot.do_cooldown('whois', msg, global_cooldown=10,
                                    local_cooldown=15)
    if cd_state:
        return
    try:
        args = arg_parser.parse_args(util_bot.delete_spammer_chrs(msg.text), {
            'id': int,
            'name': str,
            'channels': str,

            'verbose': bool,

            1: str
        }, defaults={
            'id': None,
            'name': None,

            'channels': '',

            'verbose': False,

            1: None
        })
    except arg_parser.ParserError as err:
        return f'@{msg.user}, {err.message}'
    print(args)

    if args['name'] and args[1]:
        return f'@{msg.user}, Name argument provided twice.'
    if args[1]:
        args['name'] = args[1]

    if args['id'] is not None:
        name = args['id']
        id_ = True
    elif args['name'] is not None:
        name = args['name']
        id_ = False

        if name.startswith('#'):
            id_ = True
            name = name.lstrip('#')

    else:
        return (f'@{msg.user} {msg.text.split(" ")[0]} (name:TWITCH_USERNAME|id:TWITCH_ID) [+verbose] OR '
                f'{msg.text.split(" ")[0]} TWITCH_USERNAME [+verbose]')

    async with aiohttp.request('get', f'https://api.ivr.fi/twitch/resolve/{name}',
                               params=({'id': 1}) if id_ else {},
                               headers={
                                   'User-Agent': util_bot.constants.USER_AGENT
                               }) as request:
        data = await request.json()
        if data['status'] == 404:
            return f'@{msg.user} No such user found.'

        roles = ''
        data_roles = data.get('roles', {})
        if data_roles.get('isAffiliate', False):
            roles += 'affiliate, '
        if data_roles.get('isPartner', False):
            roles += 'partner, '
        if data_roles.get('isSiteAdmin', False):
            roles += 'site admin, '
        if data_roles.get('isStaff', False):
            roles += 'staff, '
        if roles == '':
            roles = 'none'

        roles = (roles[::-1].replace(', '[::-1], '', 1))[::-1]
        # replace last ", " with "".

        if data['displayName'].casefold() != data['login'].casefold():
            login = f'({data["login"]})'
        else:
            login = ''
        print(data)

        created_at_str = ''
        for i in data['createdAt']:
            if i == '.':
                break
            created_at_str += i

        created_on = datetime.datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S')
        logo_warning = ''
        if data['logo'].startswith('https://static-cdn.jtvnw.net/user-default-pictures'):
            logo_warning = 'avatar: DEFAULT, '

        bot_notes = ''
        bot = _find_bot(data['login'])
        if bot is not None:
            if args['verbose']:
                last_active = f', Last active: {bot["lastSeen"][:-4]}' if bot['lastSeen'] is not None else ''
            else:
                last_active = ''

            bot_notes = (f' Prefix: {bot["prefix"] if bot["prefix"] is not None else "<blank>"}, '
                         f'Description: {bot["description"] if bot["description"] is not None else "<blank>"}, '
                         f'Language: {bot["language"] if bot["language"] is not None else "<unknown>"}'
                         f'{last_active}')

        info = (
            f'user {data["displayName"]}{login}',
            logo_warning,
            f'chat color: {data["chatColor"] if data["chatColor"] else "GRAY-NAME"}',
            f'account created at {created_on}',
            f'roles: {roles}',
            f'id: {data["id"]}',
            f'bio: {data["bio"]}' if data['bio'] is not None else 'empty bio',
            bot_notes
        )

        info_text = ''
        long_text = ''
        for elem in info:
            info_text += f'{elem.strip(",. ")}, ' if elem else ''
            long_text += f' - {elem.strip(",. ")}\n' if elem else ''

        ret_val = (f'@{msg.user}, {"BANNED " if data["banned"] else ""}{"bot " if data["bot"] else ""}'
                   + info_text.rstrip('., '))
        if len(ret_val) > 500:
            url = plugin_hastebin.hastebin_addr + await plugin_hastebin.upload(
                long_text
            )
            return f'@{msg.user}, Command output was too long, here\'s a hastebin: {url}'
        else:
            return ret_val


command_whois_alias = plugin_manager.add_conditional_alias('whois', plugin_prefixes.condition_prefix_exists,
                                                           return_command=True)(command_whois)
bots: typing.List[dict] = []
bots_invalidates = time.time()


async def _load_bots():
    global bots, bots_invalidates
    bots_invalidates = time.time() + 1800  # make the bot list invalidate in 30 minutes.
    async with aiohttp.request('get', 'https://supinic.com/api/bot-program/bot/list') as r:
        r: aiohttp.ClientResponse
        if r.status == 200:
            bots = (await r.json())['data']['bots']
            return 'ok'
        else:
            print(r.content)
            return f'not okay: {r.status}'


def _find_bot(username):
    for bot in bots:
        if bot['name'] == username:
            return bot
