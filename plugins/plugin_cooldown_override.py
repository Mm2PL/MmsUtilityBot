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

NAME = 'cooldown_override'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)


class Plugin(main.Plugin):
    def __init__(self, module, source):
        super().__init__(module, source)
        self.settings = [
            plugin_manager.Setting(
                owner=self,
                name='disable_channel_cooldown',
                default_value=False,
                scope=plugin_manager.SettingScope.PER_CHANNEL,
                help_='Disable per-channel cooldown in the channel. Does not impact per-user cooldowns.'
            )
        ]
        self.middleware = CooldownOverrideMiddleware()
        main.bot.middleware.append(self.middleware)

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


class CooldownOverrideMiddleware(twitchirc.AbstractMiddleware):
    def command(self, event: Event) -> None:
        cmd: main.Command = event.data.get('command')
        msg: main.StandardizedMessage = event.data.get('message')
        s = plugin_manager.channel_settings[msg.channel_ident].get('disable_channel_cooldown')
        if s:
            per_channel_key, _, _ = cmd.cooldown_keys(msg)
            legacy_global_cooldown = f'global_{msg.channel_ident}_{cmd.chat_command}'
            if legacy_global_cooldown in main.cooldowns:
                del main.cooldowns[legacy_global_cooldown]
            if per_channel_key in main.cooldowns:
                del main.cooldowns[per_channel_key]
