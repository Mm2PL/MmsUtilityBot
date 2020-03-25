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

from flask import session, abort, Response, jsonify, request

try:
    from plugins.models import channelsettings as settings_model

    # for static analysis
except ImportError:
    pass

all_settings = {}


def init(register_endpoint, ipc_conn, main_module, session_scope):
    # noinspection PyShadowingNames
    settings_model = main_module.load_model('channelsettings')
    # noinspection PyPep8Naming
    ChannelSettings, Setting = settings_model.get(main_module.Base, session_scope, all_settings)

    def check_auth(settings: ChannelSettings, s, setting_owner: main_module.User) -> bool:
        uid = session.get('user_id', None)
        if uid is not None:
            if uid == settings.channel_alias:
                return True

            user = main_module.User.get_by_twitch_id(uid)
            if setting_owner.last_known_username in user.mod_in:
                return True
        return False

    @register_endpoint('/settings/<int:channel_id>/get/<setting>')
    def get_setting(channel_id: int, setting: str):
        """Returns the setting value."""
        if channel_id == 0:  # self
            channel_id = session.get('user_id', None)
            if channel_id is None:
                abort(Response(json.dumps(
                    {
                        'status': 401,
                        'error': 'Unauthorized',
                    }
                ), content_type='application/json', status=401))
                # doesn't return
        with session_scope() as s:
            # noinspection PyProtectedMember
            target_user: main_module.User = (
                s.query(main_module.User)
                    .filter(main_module.User.twitch_id == channel_id)
                    .first()
            )
            if target_user is None:
                abort(Response(json.dumps(
                    {
                        'status': 401,
                        'error': 'Unauthorized',
                    }
                ), content_type='application/json', status=401))
                # doesn't return

            settings: ChannelSettings = (
                s.query(ChannelSettings)
                    .filter(ChannelSettings.channel_alias == target_user.id)
                    .first()
            )
            if settings:
                can_use = check_auth(settings, s, target_user)
            else:
                can_use = False

            if not can_use:
                abort(Response(json.dumps(
                    {
                        'status': 401,
                        'error': 'Unauthorized',
                    }
                ), content_type='application/json', status=401))
                # doesn't return
            try:
                if setting is '*':
                    # noinspection PyProtectedMember
                    value = settings._settings
                else:
                    value = settings.get(setting, True)
            except KeyError:
                abort(Response(json.dumps(
                    {
                        'status': 204,
                        'error': 'No content',
                        'message': 'Setting doesn\'t have a value'
                    }
                ), content_type='application/json', status=400))
            else:
                return jsonify({'status': 200, 'data': value})

    @register_endpoint('/settings/<int:channel_id>/set/<setting>')
    def set_setting(channel_id: int, setting: str):
        """Returns the setting value."""

        value = request.args.get('value', None)
        if value is None:
            abort(Response(json.dumps(
                {
                    'status': 400,
                    'error': 'Bad request'
                }
            ), status=400, content_type='application/json'))
        try:
            value = json.loads(value)
        except:
            pass

        if channel_id == 0:  # self
            channel_id = session.get('user_id', None)
            if channel_id is None:
                abort(Response(json.dumps(
                    {
                        'status': 401,
                        'error': 'Unauthorized',
                    }
                ), content_type='application/json', status=401))
                # doesn't return
        with session_scope() as s:
            # noinspection PyProtectedMember
            target_user: main_module.User = (
                s.query(main_module.User)
                    .filter(main_module.User.twitch_id == channel_id)
                    .first()
            )
            if target_user is None:
                abort(Response(json.dumps(
                    {
                        'status': 401,
                        'error': 'Unauthorized',
                    }
                ), content_type='application/json', status=401))
                # doesn't return

            settings: ChannelSettings = (
                s.query(ChannelSettings)
                    .filter(ChannelSettings.channel_alias == target_user.id)
                    .first()
            )
            if settings:
                can_use = check_auth(settings, s, target_user)
            else:
                can_use = False

            if not can_use:
                abort(Response(json.dumps(
                    {
                        'status': 401,
                        'error': 'Unauthorized',
                    }
                ), content_type='application/json', status=401))
                # doesn't return

            settings.set(setting, value, True)
            settings.update()
            s.add(settings)
            print(settings.channel_alias)
            ipc_conn.command(f'reload_settings {settings.channel_alias}'.encode())
            return jsonify({
                'status': 200
            })

