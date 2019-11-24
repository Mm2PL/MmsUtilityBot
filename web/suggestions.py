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
from flask import abort, jsonify


def init(register_endpoint, ipc_conn):
    @register_endpoint('/suggestions/list/<int:user_id>/<int:page>')
    @register_endpoint('/suggestions/list/<int:user_id>')
    def list_suggestions(user_id: int, page=0):
        ipc_conn.command(f'get_user_suggestions {user_id} {page}'.encode('utf-8'))
        msgs = ipc_conn.receive(True)
        for m in msgs:
            if m[0] == 'json' and m[1]['type'] == 'suggestion_list':
                return jsonify({
                    'status': 200,
                    'page': m[1]['page'],
                    'page_size': m[1]['page_size'],  # don't copy shit you don't need to, leaking info is bad.
                    'data': m[1]['data']
                })
        abort(400)  # bad request
