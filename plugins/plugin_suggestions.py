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


    __tablename__ = 'suggestions'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    author_alias = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'))
    author = relationship('User')

    text = sqlalchemy.Column(sqlalchemy.Text)
    state = sqlalchemy.Column(sqlalchemy.Enum(SuggestionState))
    notes = sqlalchemy.Column(sqlalchemy.Text)

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
    t = main.delete_spammer_chrs(msg.text).split(' ', 1)
    if len(t) == 1:
        main.bot.send(msg.reply(f'@{msg.user}, Usage: suggest <text...>'))
        return

    s = Suggestion(author=main.User.get_by_message(msg), text=t[1], state=Suggestion.SuggestionState.new,
                   notes='<no notes>')
    with main.session_scope() as session:
        session.add(s)
    main.bot.send(msg.reply(f'@{msg.user} Suggestion saved, hopefully. ID: {s.id}'))


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
        main.bot.send(msg.reply(f'@{msg.user}, Usage: check_suggestion <ID> or check_suggestion.'))
        return
    target = t[1]
    if target.isnumeric():
        target = int(target)
        with main.session_scope() as session:
            suggestion = session.query(Suggestion).filter(Suggestion.id == target).first()
            main.bot.send(msg.reply(f'@{msg.user} '
                                    f'{suggestion.humanize(suggestion.author.last_known_username == msg.user)}'))
    else:
        with main.session_scope() as session:
            user = main.User.get_by_message(msg, no_create=True)
            if user is None:
                main.bot.send(msg.reply(f'@{msg.user}, You are a new user, you don\'t have any suggestions.'))
                return
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
        main.bot.send(msg.reply(f'@{msg.user}, Usage: resolve_suggestion <ID> <state> [notes...]'))
        return

    if not t[1].isnumeric():
        main.bot.send(msg.reply(f'@{msg.user}, Unknown suggestion {t[1]!r}.'))
        return
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

