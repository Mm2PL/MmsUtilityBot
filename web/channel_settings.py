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
import textwrap
import time
import typing

import twitchirc
from flask import session, abort, Response, jsonify, request, render_template, flash, redirect
from markupsafe import Markup

from web import tables

try:
    from plugins.models import channelsettings as settings_model

    # for static analysis
except ImportError:
    pass

all_settings = {}
settings_next_refresh = time.time()


def init(register_endpoint, ipc_conn, main_module, session_scope):
    # noinspection PyShadowingNames
    settings_model = main_module.load_model('channelsettings')
    # noinspection PyPep8Naming
    ChannelSettings, Setting = settings_model.get(main_module.Base, session_scope, all_settings)

    def _prase_setting_scope(scope):
        return settings_model.SettingScope[scope]

    def _parse_settings(data: typing.Dict[str, dict]):
        for k, v in data.items():
            setting = Setting(v['owner_name'], v['name'],
                              v['default_value'] if v['default_value'] != '...' else ...,
                              _prase_setting_scope(v['scope']),
                              v['write_defaults'],
                              v['setting_type'],
                              help_=v['help'])
            all_settings[k] = setting

    def _refetch_settings():
        global all_settings, settings_next_refresh
        if settings_next_refresh < time.time():
            settings_next_refresh = time.time() + 600
            ipc_conn.command(b'all_settings')
            has_received = False
            while not has_received:
                msgs = ipc_conn.receive(recv_until_complete=True)
                for msg in msgs:
                    if msg[0] == 'json' and msg[1]['source'] == 'all_settings':
                        all_settings.clear()
                        _parse_settings(msg[1]['data'])
                        has_received = True
                        break

    def check_auth(settings: ChannelSettings, s, setting_owner: main_module.User) -> bool:
        uid = session.get('user_id', None)
        if uid is not None:
            if uid == settings.channel_alias:
                return True

            user = main_module.User.get_by_twitch_id(uid)
            if (setting_owner.last_known_username in user.mod_in
                    or f'settings.{setting_owner.twitch_id}' in user.permissions
                    or twitchirc.GLOBAL_BYPASS_PERMISSION in user.permissions):
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
                if setting == '*':
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
                ), content_type='application/json', status=204))
            else:
                return jsonify({'status': 200, 'data': value})

    @register_endpoint('/settings/<int:channel_id>/set/<setting>')
    def set_setting(channel_id: int, setting: str):
        """Changes the setting value."""

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

    @register_endpoint('/settings/<int:channel_id>/unset/<setting>')
    def unset_setting(channel_id: int, setting: str):
        """Set a setting to the default"""

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
                settings.unset(setting, True)
            except KeyError:
                abort(Response(json.dumps(
                    {
                        'status': 410,
                        'error': 'Gone',
                        'message': 'Setting doesn\'t have a value, so there\'s nothing to remove.'
                    }
                ), content_type='application/json', status=410))
                # doesn't return

            settings.update()
            s.add(settings)
            print(settings.channel_alias)
            ipc_conn.command(f'reload_settings {settings.channel_alias}'.encode())
            return jsonify({
                'status': 200
            })

    @main_module.app.route('/settings/global/get/<setting>')
    def global_get_setting(setting: str):
        return get_setting(-1, setting)

    @main_module.app.route('/settings/global/set/<setting>')
    def global_set_setting(setting: str):
        return set_setting(-1, setting)

    @main_module.app.route('/settings/global/unset/<setting>')
    def global_unset_setting(setting: str):
        return unset_setting(-1, setting)

    @main_module.app.route('/settings/<int:channel_id>')
    def setting_ui(channel_id: int):
        if session.get('user_id') is None:
            return render_template('403.html')

        if channel_id == 0:
            channel_id = session.get('user_id')
            return redirect(f'/settings/{channel_id}')

        _refetch_settings()
        with session_scope() as s:
            # noinspection PyProtectedMember
            target_user: main_module.User = (
                s.query(main_module.User)
                    .filter(main_module.User.twitch_id == channel_id)
                    .first()
            )
            if target_user is None:
                return render_template('404.html')

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
                return render_template('no_perms.html')

            current_scope = 'PER_CHANNEL' if channel_id != -1 else 'GLOBAL'
            return tables.render_table(
                'Settings list',
                [
                    [
                        Markup('<em>%s</em>') % setting.owner,
                        setting.name,
                        _styled_setting_value(setting, settings),
                        Markup('<a href="%s/%s">Edit</a>') % (
                            'global' if channel_id == -1 else channel_id, setting.name
                        ),
                        Markup('<br>').join(
                            setting.help.split('\n')
                        )
                    ] for name, setting in all_settings.items()
                    if setting.scope.name == current_scope
                ],
                header=[
                    ('provided_by', 'Plugin'),
                    ('name', 'Setting name'),
                    ('value', 'Value'),
                    ('actions', 'Actions'),
                    ('help', 'Help'),
                ]
            )

    def _styled_setting_value(s, settings) -> Markup:
        nice_value = (('[default]' if s.name not in settings._settings else '')
                      + json.dumps(settings.get(s)))
        value = settings.get(s)
        if s.setting_type == 'bool':
            return value
        else:
            return Markup('%s') % (nice_value,)

    @main_module.app.route('/settings/<int:channel_id>/<setting>')
    def edit_setting_ui(channel_id: int, setting: str):
        if session.get('user_id') is None:
            return render_template('403.html')

        if channel_id == 0:
            channel_id = session.get('user_id')
        _refetch_settings()
        with session_scope() as s:
            # noinspection PyProtectedMember
            target_user: main_module.User = (
                s.query(main_module.User)
                    .filter(main_module.User.twitch_id == channel_id)
                    .first()
            )
            if target_user is None:
                return render_template('no_perms.html')

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
                return render_template('no_perms.html')

            setting = all_settings.get(setting)
            if setting is None:
                abort(Response(
                    'Bad request: invalid setting given.',
                    status=400, mimetype='text/plain'
                ))
            flash_message = request.args.get('flash')
            if flash_message:
                flash(flash_message)

            channel_name_or_global = f'in #{target_user.last_known_username}' if channel_id != -1 else 'global setting'
            return tables.render_table(
                f'Edit setting {setting.name} ({channel_name_or_global})',
                [
                    [
                        'Type',
                        setting.setting_type if setting.setting_type is not None else 'unknown (setting as JSON)'
                    ],
                    [
                        'Current value',
                        _styled_setting_value(setting, settings)
                    ],
                    [
                        'Default value',
                        Markup('%s <button onclick="unset();">Set to default</button>') % (setting.default_value,)
                    ],
                    [
                        'Edit value',
                        _edit_box_for_setting(setting, settings)
                    ],
                    [
                        Markup('<button onclick="submit();">Submit</button>'),
                        Markup('<a href="../{target}">Back to the list settings.</a>')
                            .format(target='global' if channel_id == -1 else channel_id)
                    ]
                ],
                header=[
                    ('key', 'Name'),
                    ('value', 'Value'),
                ],
                extra_markup=_make_edit_setting_js(setting, channel_id, request.args.get('return_to'))
            )

    def _make_edit_setting_js(setting, channel_id, return_to) -> Markup:
        channel_id_or_global = 'global' if channel_id == -1 else channel_id
        code = textwrap.dedent(f"""
        const setting_type = {json.dumps(setting.setting_type)};
        const setting_name = {json.dumps(setting.name)};
        const channel_id_or_global = {json.dumps(channel_id_or_global)};
        const return_to = encodeURIComponent({json.dumps(return_to)});
        
        function update_background() {{
            if (setting_type === 'bool') {{
                const value_box = document.getElementById("set_setting_value");
                const value = value_box.checked;
                console.log(value);
                if (value) {{
                    value_box.parentElement.style.background = '#00aa00';
                }} else {{
                    value_box.parentElement.style.background = '#aa0000';
                }}
            }}
        }}

        async function submit() {{
            const value_box = document.getElementById("set_setting_value");
            const c_id = channel_id_or_global;
            let value;
            if (setting_type === 'bool') {{
                value = value_box.checked;
            }}
            else {{
                value = value_box.value;
            }}
            const request = await fetch(`/settings/${{c_id}}/set/${{setting_name}}?value=${{value}}`);
            window.location = (
                    `${{window.location.origin}}${{window.location.pathname}}?flash=Value(${{value}}) has been set`
                    + `&return_to=${{return_to}}`
            );
        }}

        async function unset() {{
            const c_id = channel_id_or_global;

            const request = await fetch(`/settings/${{c_id}}/unset/${{setting.name}}`);
            window.location = (
                    `${{window.location.origin}}${{window.location.pathname}}?flash=Value has been unset`
            );
        }}

        update_background();
        """)
        return Markup('<script type=application/javascript>{}</script>'.format(code))

    def _edit_box_for_setting(setting, settings):
        if setting.setting_type in ['int', 'float']:
            return Markup('<input id="set_setting_value" type="number" value="{value}" '
                          'step={step}>').format(
                value=settings.get(setting),
                step='any' if setting.setting_type == 'float' else '1'
            )
        elif setting.setting_type == 'bool':
            return (Markup('<input id="set_setting_value" type="checkbox" {checked} '
                           'onclick="update_background();">')
                    .format(checked='checked' if settings.get(setting) else ''))
        else:
            return (Markup('<input id="set_setting_value" type="text" value="{value}">')
                    .format(value=_styled_setting_value(setting, settings)))

    @main_module.app.route('/settings/global')
    def _global_setting_ui():
        return setting_ui(-1)

    @main_module.app.route('/settings/global/<setting>')
    def _global_edit_setting_ui(setting: str):
        return edit_setting_ui(-1, setting)
