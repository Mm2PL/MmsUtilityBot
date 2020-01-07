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
import datetime
import enum

import sqlalchemy
from sqlalchemy.orm import relationship

def get(Base):
    class Suggestion(Base):
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
            st = self.state.name.replace('_', ' ')
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


    return Suggestion
