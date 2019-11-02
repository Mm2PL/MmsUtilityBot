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
import twitchirc
import enum
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

    def __repr__(self):
        return f'<{self.state.name.capitalize()} suggestion {self.id} by {self.author.last_known_username}>'


@plugin_help.add_manual_help_using_command('Suggest something. You can use this to report a bug, '
                                           'request a feature etc.',
                                           ['suggest'])
@plugin_manager.add_conditional_alias('suggest', plugin_prefixes.condition_prefix_exists)
@main.bot.add_command('mb.suggest')
def command_suggest(msg: twitchirc.ChannelMessage):
    cd_state = main.do_cooldown('suggest', msg, global_cooldown=0, local_cooldown=30)
    if cd_state:
        return
    t = msg.text.split(' ', 1)
    if len(t) == 1:
        bot.send(msg.reply(f'@{msg.user}, Usage: suggest <text...>'))
        return

    s = Suggestion(author=main.User.get_by_message(msg), text=t[1], state=Suggestion.SuggestionState.new,
                   notes='<no notes>')
    with main.session_scope() as session:
        session.add(s)
    main.bot.send(msg.reply(f'@{msg.user} Suggestion saved, hopefully.'))
