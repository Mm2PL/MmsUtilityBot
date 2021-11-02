#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
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
import json
import typing

import grpc

import util_bot
import util_bot.rpc.compiled.bot_pb2_grpc as bot_pb2_grpc
import util_bot.rpc.compiled.bot_pb2 as bot_pb2


class BotServiceImpl(bot_pb2_grpc.BotServicer):
    def get_all_settings(self, request: bot_pb2.NullRequest, context) -> bot_pb2.AllSettingsResponse:
        plugin_man = util_bot.plugins['plugin_manager'].module
        if typing.TYPE_CHECKING:
            import plugins.plugin_manager as plugin_man

        output = {}
        for k, v in plugin_man.all_settings.items():
            output[k] = bot_pb2.SettingResponse(**{
                'owner_name': v.owner.name,
                'name': v.name,
                'default_value': '...' if v.default_value is ... else json.dumps(v.default_value),
                'scope': v.scope.name,
                'write_defaults': v.write_defaults,
                'setting_type': v.setting_type.__name__ if hasattr(v.setting_type, '__name__') else str(v.setting_type),
                'help': v.help
            })
        return bot_pb2.AllSettingsResponse(all_settings=output)

    def reload_settings(self, request: bot_pb2.ChannelRequest, context) -> bot_pb2.OptionMessage:
        plugin_man = util_bot.plugins['plugin_manager'].module
        if typing.TYPE_CHECKING:
            import plugins.plugin_manager as plugin_man
        channel = request.channel_id
        if channel != -1:
            user = util_bot.User.get_by_local_id(channel)
            if not user or user.last_known_username not in plugin_man.channel_settings:
                return bot_pb2.OptionMessage(ok=False, message='A user with this ID is not known to this bot.')
            else:
                print(f'update settings for {channel!r} (#{user.last_known_username!r})')
                del plugin_man.channel_settings[user.last_known_username]
                with util_bot.session_scope() as session:
                    settings = (session.query(plugin_man.ChannelSettings)
                                .filter(plugin_man.ChannelSettings.channel_alias == user.id)
                                .first())
                    plugin_man.channel_settings[user.last_known_username] = settings
                return bot_pb2.OptionMessage(ok=True)
        else:
            print(f'update settings for {channel!r} (GLOBAL)')
            del plugin_man.channel_settings['GLOBAL']
            with util_bot.session_scope() as session:
                settings = (session.query(plugin_man.ChannelSettings)
                            .filter(plugin_man.ChannelSettings.channel_alias == -1)
                            .first())
                plugin_man.channel_settings['GLOBAL'] = settings
            return bot_pb2.OptionMessage(ok=True)
