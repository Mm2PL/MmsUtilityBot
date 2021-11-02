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
import typing

from flask import render_template, session, jsonify
from markupsafe import Markup

from . import tables

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import app


def init(register_endpoint, main_module, session_scope):
    if typing.TYPE_CHECKING:
        User = app.User
    else:
        User = main_module.User

    def get_editable_channels() -> typing.Set[User]:
        targets = set()
        with session_scope() as sesh:
            current_user = User.get_by_twitch_id(session.get('user_id'), session=sesh)
            for perm in current_user.permissions:
                if perm.startswith('settings.'):
                    target_id = perm.replace('settings.', '', 1)
                    targets.add(User.get_by_twitch_id(target_id, session=sesh))

            for mod in current_user.mod_in:
                target_user = User.get_by_name(mod, s=sesh)
                if len(target_user) == 1:
                    targets.add(target_user[0])
        return targets

    @register_endpoint('/channels/list')
    def editable_channels() -> typing.List[typing.Dict[str, typing.Union[int, str]]]:
        """
        Lists all available channels for the current user.

        :returns: Object of {name, id}
        """
        if session.get('user_id') is None:
            return render_template('403.html')
        channels = get_editable_channels()
        print([i.last_known_username for i in channels])

        for i in channels.copy():
            if i.id == -2 and i.last_known_username == 'whispers':
                channels.remove(i)
        return jsonify([
            {
                "name": i.last_known_username,
                "id": i.twitch_id
            } for i in channels
        ])

    @main_module.app.route('/channels')
    def editable_channels_ui():
        if session.get('user_id') is None:
            return render_template('403.html')
        channels = get_editable_channels()
        print([i.last_known_username for i in channels])

        for i in channels.copy():
            if i.id == -2 and i.last_known_username == 'whispers':
                channels.remove(i)

        data = [
            [
                '#' + i.last_known_username, Markup(f'<a href="/settings/{i.twitch_id}">Settings</a>')
            ]
            if i.id != -1 else
            [
                'Global', Markup('<a href="/settings/global">Settings</a>')
            ]
            for i in channels
        ]
        data.sort(key=lambda entry: entry[0])
        return tables.render_table('List of channels', data, [('Name', 'name'), ('Edit Settings', 'edit_settings')])
