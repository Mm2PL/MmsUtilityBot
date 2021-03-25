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
import typing

import aiohttp

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
main.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit(1)
try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'hastebin'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.hastebin_addr_setting = plugin_manager.Setting(
            owner=self,
            name='hastebin.address',
            default_value='https://hastebin.com/',
            scope=plugin_manager.SettingScope.GLOBAL,
            write_defaults=True
        )
        self.c_hastebin = main.bot.add_command(
            'hastebin',
            cooldown=main.CommandCooldown(30, 0, 0)
        )(self.c_hastebin)
        plugin_help.add_manual_help_using_command('Create a hastebin of the message you provided.')(self.c_hastebin)

    @property
    def hastebin_addr(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].get(self.hastebin_addr_setting)

    async def upload(self, data: str, expire_date: typing.Optional[datetime.datetime] = None):
        params = {}
        if expire_date:
            params['expire_time'] = expire_date.isoformat()

        async with aiohttp.request(
                'post',
                f'{self.hastebin_addr}documents',
                data=data.encode('utf-8'),
                params=params
        ) as r:
            response = await r.json()
            return response['key']

    async def c_hastebin(self, msg: twitchirc.ChannelMessage):
        data = main.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 1)[1]

        link = await self.upload(data)
        return f'@{msg.user} Here\'s your hastebin link {self.hastebin_addr}{link}'

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return super().commands

    @property
    def on_reload(self):
        return super().on_reload
