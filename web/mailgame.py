#  This is a simple utility bot
#  Copyright (C) 2021 Mm2PL
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

# noinspection PyUnresolvedReferences
import typing

import twitchirc
from flask import session, render_template
from markupsafe import Markup, escape

if typing.TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import app

import tables


def init(register_endpoint, ipc_conn, main_module, session_scope):
    if typing.TYPE_CHECKING:
        User = app.User
        main_module = app
        import plugins.models.mailbox_game as mailbox_game
        MailboxGame = mailbox_game.get(main_module.Base)
    else:
        User = main_module.User
        MailboxGame = main_module.load_model('mailbox_game').get(main_module.Base)

    def check_auth() -> bool:
        uid = session.get('user_id', None)
        if uid is not None:
            with session_scope() as s:
                user = User._get_by_twitch_id(uid, s)
            if (f'mailgame.view' in user.permissions
                    or twitchirc.GLOBAL_BYPASS_PERMISSION in user.permissions):
                return True
        return False

    @main_module.app.route('/mailgame')
    def list_games():
        if not check_auth():
            return render_template('no_perms.html')
        with session_scope() as sesh:
            games: typing.List[MailboxGame] = sesh.query(MailboxGame).all()
            # best: List[Dict[str,Union[int,str]]]
            output = [
                [
                    Markup(f'<a href=./mailgame/{i.id}>{i.id}</a>'),
                    i.channel.last_known_username,
                    repr(i.scores).strip('[]'),
                    f'{len(list(filter(lambda o: o["quality"] == 3, i.winners)))} winners'
                ]
                for i in games
            ]
        return tables.render_table(
            'Mailgame saved records',
            data=output,
            header=[
                ('id', 'id'),
                ('channel', 'channel'),
                ('winning scores', 'winning_scores'),
                ('winners', 'winners'),
            ]
        )

    @main_module.app.route('/mailgame/<int:game_id>')
    def view_specific_game(game_id: int):
        if not check_auth():
            return render_template('no_perms.html')
        with session_scope() as sesh:
            try:
                game: MailboxGame = sesh.query(MailboxGame).filter(MailboxGame.id == game_id).one()
            except:
                return render_template('404.html')

            # best: List[Dict[str,Union[int,str]]]
            output = [
                [
                    'ID',
                    game.id,
                ],
                [
                    'Channel',
                    game.channel.last_known_username,
                ],
                [
                    'Winning scores',
                    repr(game.scores).strip('[]'),
                ],
                [
                    'Settings',
                    Markup('<br>'.join([
                        f'{k}: {v}'
                        for k, v in game.settings.items()
                    ]))
                ],
                [
                    'Best guesses',
                    Markup('<br>'.join([
                        f"{i['quality']}/3 {escape(i['msg'])}" for i in game.winners
                    ]))
                ],
                [
                    'All guesses',
                    Markup('<br>'.join([
                        f"{i['quality']}/3 {escape(i['msg'])}" for i in game.guesses
                    ]))
                ]
            ]
        return tables.render_table(
            'Mailgame saved records',
            data=output,
            header=[
                ('key', 'key'),
                ('value', 'value'),
            ]
        )
