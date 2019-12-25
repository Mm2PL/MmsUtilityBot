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
from flask import abort, jsonify


def init(register_endpoint, ipc_conn):
    @register_endpoint('/suggestions/list/user/<int:user_id>/<int:page>')
    def list_suggestions(user_id: int, page=0):
        """
        List suggestions filtering by user.
        <br/>
        Arguments:
        <ol>
            <li>
            <b>user_id</b> Internal id of the user you want to search for. NOT THE TWITCH ID.
            </li>

            <li>
            <b>page</b> Page number you want. Pages are 50 or less entries in size, indexed from 0.
            </li>
        </ol>
        """
        ipc_conn.command(f'get_user_suggestions {user_id} {page}'.encode('utf-8'))
        msgs = ipc_conn.receive(True, recv_until_complete=True)
        for m in msgs:
            if m[0] == 'json' and m[1]['type'] == 'suggestion_list':
                return jsonify({
                    'status': 200,
                    'page': m[1]['page'],
                    'page_size': m[1]['page_size'],  # don't copy shit you don't need to, leaking info is bad.
                    'data': m[1]['data']
                })
        abort(400)  # bad request

    @register_endpoint('/suggestions/list/<int:page>')
    def list_all_suggestions(page):
        """
        List suggestions
        <br/>
        Arguments:
        <ol>
            <li>
            <b>page</b> Page number you want. Pages are 50 or less entries in size, indexed from 0.
            </li>
        </ol>
        """
        ipc_conn.command(f'get_suggestions {page}'.encode('utf-8'))
        msgs = ipc_conn.receive(True, True)
        print(msgs)
        for m in msgs:
            if m[0] == 'json' and m[1]['type'] == 'suggestion_list':
                return jsonify({
                    'status': 200,
                    'page': m[1]['page'],
                    'page_size': m[1]['page_size'],  # don't copy shit you don't need to, leaking info is bad.
                    'data': m[1]['data']
                })
        abort(400)  # bad request
