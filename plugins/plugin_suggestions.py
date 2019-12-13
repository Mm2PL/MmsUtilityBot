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
import enum

import twitchirc
import sqlalchemy
from sqlalchemy.orm import relationship
import socket
import threading
import datetime

try:
    # noinspection PyUnresolvedReferences
    import main
except ImportError:
    # noinspection PyPackageRequirements
    import util_bot as main

    raise

main.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    import plugins.plugin_help as plugin_help

    exit(1)

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

    exit(1)

main.load_file('plugins/plugin_prefixes.py')
try:
    import plugin_plugin_prefixes as plugin_prefixes
except ImportError:
    import plugins.plugin_prefixes as plugin_prefixes

    exit(1)
main.load_file('plugins/plugin_ipc.py')
try:
    import plugin_plugin_ipc as plugin_ipc
except ImportError:
    import plugins.plugin_ipc as plugin_ipc

    exit(1)

__meta_data__ = {
    'name': 'suggestions',
    'commands': []
}
log = main.make_log_function('suggestions')


class Suggestion(main.Base):
    class SuggestionState(enum.Enum):
        new = 0
        done = 1
        accepted = 2
        rejected = 3
        not_a_suggestion = 4
        duplicate = 5


    __tablename__ = 'suggestions'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    author_alias = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'))
    author = relationship('User')

    text = sqlalchemy.Column(sqlalchemy.Text)
    state = sqlalchemy.Column(sqlalchemy.Enum(SuggestionState))
    notes = sqlalchemy.Column(sqlalchemy.Text)

    creation_date = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True, default=datetime.datetime.now)
    is_hidden = sqlalchemy.Column(sqlalchemy.Boolean, default=False)

    def nice_state(self, capitalize=False):
        st = self.state.name.replace('_', '')
        if capitalize:
            return st.capitalize()
        else:
            return st

    def __repr__(self):
        return f'<{self.nice_state(True)} suggestion {self.id} by {self.author.last_known_username}>'

    def humanize(self, as_author=False):
        if as_author:
            if self.notes not in [None, '<no notes>']:
                return f'{self.text} (id: {self.id}, state: {self.nice_state()}, notes: {self.notes})'
            else:
                return f'{self.text} (id: {self.id}, state: {self.nice_state()})'
        else:
            if self.notes not in [None, '<no notes>']:
                return (f'{self.text} (id: {self.id}, state: {self.nice_state()}, '
                        f'author: {self.author.last_known_username}, notes: {self.notes})')
            else:
                return (f'{self.text} (id: {self.id}, state: {self.nice_state()}, '
                        f'author: {self.author.last_known_username})')


@plugin_help.add_manual_help_using_command('Suggest something. You can use this to report a bug, '
                                           'request a feature etc.',
                                           ['suggest'])
@plugin_manager.add_conditional_alias('suggest', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.suggest')
def command_suggest(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('suggest', msg, global_cooldown=0, local_cooldown=30)
    if cd_state:
        return
    t = main.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 1)
    if len(t) == 1:
        return f'@{msg.user}, Usage: suggest <text...>'

    s = Suggestion(author=main.User.get_by_message(msg), text=t[1], state=Suggestion.SuggestionState.new,
                   notes='<no notes>')
    with main.session_scope() as session:
        session.add(s)
    return f'@{msg.user} Suggestion saved, hopefully. ID: {s.id}'


@plugin_help.add_manual_help_using_command('Check on your suggestions.',
                                           ['check_suggestion'])
@plugin_manager.add_conditional_alias('check_suggestion', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.check_suggestion')
def command_check_suggestion(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('check_suggestion', msg, global_cooldown=0, local_cooldown=30)
    if cd_state:
        return
    t = main.delete_spammer_chrs(msg.text).split(' ')
    if len(t) == 1:
        return f'@{msg.user}, Usage: check_suggestion <ID> or check_suggestion.'
    target = t[1]
    if target.isnumeric():
        target = int(target)
        with main.session_scope() as session:
            suggestion = session.query(Suggestion).filter(Suggestion.id == target).first()
            if suggestion is None:
                return f'@{msg.user} Suggestion id {target!r} not found.'
            else:
                main.bot.send(msg.reply(f'@{msg.user} '
                                        f'{suggestion.humanize(suggestion.author.last_known_username == msg.user)}'))
    else:
        with main.session_scope() as session:
            user = main.User.get_by_message(msg, no_create=True)
            if user is None:
                return f'@{msg.user}, You are a new user, you don\'t have any suggestions.'
            suggestions = (session.query(Suggestion)
                           .filter(Suggestion.author == user)
                           .filter(Suggestion.state.notin_([Suggestion.SuggestionState.done,
                                                            Suggestion.SuggestionState.rejected,
                                                            Suggestion.SuggestionState.not_a_suggestion])))
            main.bot.send(msg.reply(f'@{msg.user} Your suggestions: '
                                    f'{", ".join([f"{s.id} ({s.nice_state()})" for s in suggestions])}'))


@plugin_help.add_manual_help_using_command('Mark a suggestion as resolved.',
                                           ['resolves',
                                            'resolve_suggestion'])
@plugin_manager.add_conditional_alias('resolves', plugin_prefixes.condition_prefix_exists)
@plugin_manager.add_conditional_alias('resolve_suggestion', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.resolve_suggestion', required_permissions=['suggestions.resolve'])
def command_resolve_suggestion(msg: twitchirc.ChannelMessage):
    t = main.delete_spammer_chrs(msg.text).split(' ', 3)
    if len(t) < 3:
        return f'@{msg.user}, Usage: resolve_suggestion <ID> <state> [notes...]'

    if not t[1].isnumeric():
        return f'@{msg.user}, Unknown suggestion {t[1]!r}.'
    target = int(t[1])
    state_names = [i.name for i in Suggestion.SuggestionState]
    if t[2] in state_names:
        state = Suggestion.SuggestionState[t[2]]
    else:
        main.bot.send(msg.reply(f'@{msg.user}, Invalid state: {t[2]!r}. Choose between '
                                f'{", ".join([repr(i.name) for i in Suggestion.SuggestionState])}'))
        return
    if len(t) == 4:
        notes = t[3]
    else:
        notes = None
    with main.session_scope() as session:
        suggestion = session.query(Suggestion).filter(Suggestion.id == target).first()
        suggestion.state = state
        if notes is not None:
            suggestion.notes = notes
        session.add(suggestion)
    main.bot.send(msg.reply(f'@{msg.user} Modified suggestion id {target!r}, '
                            f'new state {state}, '
                            f'new notes {notes}.'))


PAGE_SIZE = 50


@plugin_ipc.add_command('get_user_suggestions')
def _ipc_command_list_suggestions(sock: socket.socket, msg: str, socket_id):
    arg: str
    _, arg = msg.replace('\n', '').replace('\r\n', '').split(' ', 1)
    args = arg.split(' ', 1)
    user_id = None
    page_num = None
    if len(args) >= 2:
        if args[0].isnumeric():
            user_id = int(args[0])
        if args[1].isnumeric():
            page_num = int(args[1])
    if user_id is None or page_num is None:
        return (b'!1\r\n'
                b'~Invalid usage.\r\n'
                +
                plugin_ipc.format_json(
                    {
                        'type': 'error',
                        'source': 'get_user_suggestions',
                        'message': 'Invalid usage.'
                    })
                )
    else:
        def _fetch_suggestions(rwq):
            print(f'fetch {user_id} p {page_num}')
            with main.session_scope() as session:
                suggestions = (session.query(Suggestion)
                               .filter(Suggestion.author_alias == user_id)
                               .offset(page_num * PAGE_SIZE)
                               .limit(PAGE_SIZE)
                               .all())
                rwq.put(
                    plugin_ipc.format_json(
                        {
                            'type': 'suggestion_list',
                            'page': page_num,
                            'page_size': PAGE_SIZE,
                            'data': [
                                {
                                    'text': suggestion.text,
                                    'notes': suggestion.notes,
                                    'state': suggestion.state.name,
                                    'id': suggestion.id
                                }
                                for suggestion in suggestions
                            ]
                        }
                    )
                )

        t = threading.Thread(target=_fetch_suggestions, args=(plugin_ipc.response_write_queues[socket_id],))
        t.start()


@plugin_ipc.add_command('get_suggestion')
def _ipc_command_list_suggestions(sock: socket.socket, msg: str, socket_id):
    arg: str
    _, arg = msg.replace('\n', '').replace('\r\n', '').split(' ', 1)
    args = arg.split(' ', 1)
    suggestion_id = None
    if len(args) >= 1:
        if args[0].isnumeric():
            suggestion_id = int(args[0])
    if suggestion_id is None:
        return (b'!1\r\n'
                b'~Invalid usage.\r\n'
                +
                plugin_ipc.format_json(
                    {
                        'type': 'error',
                        'source': 'get_suggestion',
                        'message': 'Invalid usage.'
                    })
                )
    else:
        def _fetch_suggestions(rwq):
            print(f'fetch suggestion {suggestion_id}')
            with main.session_scope() as session:
                suggestion = (session.query(Suggestion)
                              .filter(Suggestion.id == suggestion_id)
                              .first())
                rwq.put(
                    plugin_ipc.format_json(
                        {
                            'type': 'suggestion_list',
                            'page': 0,
                            'page_size': 1,
                            'data':
                                ([
                                     {
                                         'text': suggestion.text,
                                         'notes': suggestion.notes,
                                         'state': suggestion.state.name,
                                         'id': suggestion.id,
                                         'author': {
                                             'name': suggestion.author.last_known_username,
                                             'alias': suggestion.author.id
                                         }
                                     }
                                 ] if suggestion is not None else [])
                        }
                    )
                )

        t = threading.Thread(target=_fetch_suggestions, args=(plugin_ipc.response_write_queues[socket_id],))
        t.start()


@plugin_ipc.add_command('get_suggestions')
def _ipc_command_list_suggestions(sock: socket.socket, msg: str, socket_id):
    arg: str
    _, arg = msg.replace('\n', '').replace('\r\n', '').split(' ', 1)
    args = arg.split(' ', 1)
    page_num = None
    if len(args) >= 1:
        if args[0].isnumeric():
            page_num = int(args[0])
    if page_num is None:
        return (b'!1\r\n'
                b'~Invalid usage.\r\n'
                +
                plugin_ipc.format_json(
                    {
                        'type': 'error',
                        'source': 'get_user_suggestions',
                        'message': 'Invalid usage.'
                    })
                )
    else:
        def _fetch_suggestions(rwq):
            print(f'fetch suggestions, p {page_num}')
            with main.session_scope() as session:
                suggestions = (session.query(Suggestion)
                               .offset(page_num * PAGE_SIZE)
                               .limit(PAGE_SIZE)
                               .all())
                rwq.put(
                    plugin_ipc.format_json(
                        {
                            'type': 'suggestion_list',
                            'page': page_num,
                            'page_size': PAGE_SIZE,
                            'data': [
                                {
                                    'text': suggestion.text,
                                    'notes': suggestion.notes,
                                    'state': suggestion.state.name,
                                    'id': suggestion.id,
                                    'author': {
                                        'name': suggestion.author.last_known_username,
                                        'alias': suggestion.author.id
                                    }
                                }
                                for suggestion in suggestions
                            ]
                        }
                    )
                )

        t = threading.Thread(target=_fetch_suggestions, args=(plugin_ipc.response_write_queues[socket_id],))
        t.start()
