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

import typing
from types import FunctionType

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
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'no_perm_message'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)
NO_PERM_IGNORE = 0
NO_PERM_MESSAGE = 1


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        for h in main.bot.handlers['permission_error'].copy():
            h: FunctionType
            if h.__name__ == 'permission_error_handler':
                main.bot.handlers['permission_error'].remove(h)
        main.bot.handlers['permission_error'].append(self._no_permission_handler)
        self.no_perm_handler = plugin_manager.Setting(self,
                                                      'no_perm_handler',
                                                      default_value=NO_PERM_MESSAGE,
                                                      scope=plugin_manager.SettingScope.PER_CHANNEL,
                                                      help_=(
                                                          f'Changes behaviour when a user tries to use a command they '
                                                          f'don\'t have permission to use. \n'
                                                          f'If set to {NO_PERM_MESSAGE} a message will be shown to the '
                                                          f'user saying that they are missing permissions, \n'
                                                          f'otherwise this kind of event will be ignored and no '
                                                          f'messages will be shown.'
                                                      ))

    def _no_permission_handler(self, event, message: twitchirc.ChannelMessage,
                               command: typing.Optional[twitchirc.Command], missing_permissions: typing.List[str]):
        del event
        if command is None:  # ignore cooldown bypass checks
            return
        if message.channel in plugin_manager.channel_settings:
            settings = plugin_manager.channel_settings[message.channel]
            if settings.get(self.no_perm_handler.name) == NO_PERM_MESSAGE:
                main.bot.send(message.reply(f"@{message.user} You are missing permissions "
                                            f"({', '.join(missing_permissions)}) to use command "
                                            f"{command.chat_command}."))

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
