#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
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
import typing

from twitchirc import Event

from util_bot import Platform

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'autorefresh'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        main.bot.clients[Platform.TWITCH].middleware.append(AutorefreshMiddleware())

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


class AutorefreshMiddleware(twitchirc.AbstractMiddleware):
    def __init__(self):
        super().__init__()
        self.is_reconnect = False

    def reconnect(self, event: Event) -> None:
        log('info', 'Received reconnect event.\n'
                    'Attempting token refresh...')
        main.twitch_auth.refresh()
        main.twitch_auth.save()
        log('info', 'Refreshed and saved.')
        # noinspection PyProtectedMember
        main.bot.clients[Platform.TWITCH].connection._password = 'oauth:' + main.twitch_auth.json_data['access_token']
