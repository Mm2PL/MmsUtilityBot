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
import json
import typing

import sqlalchemy
from sqlalchemy.orm import relationship
from sqlalchemy import Column, ForeignKey


def get(Base):
    class MailboxGame(Base):
        __tablename__ = 'mailbox_game'
        id = Column(sqlalchemy.Integer, primary_key=True)

        channel_alias = Column(sqlalchemy.Integer, ForeignKey('users.id'))
        channel = relationship('User')

        scores_raw = Column(sqlalchemy.Text)

        creation_date = Column(sqlalchemy.DateTime, default=datetime.datetime.now)
        settings_raw = Column(sqlalchemy.Text)

        winners_raw = Column(sqlalchemy.Text)
        guesses_raw = Column(sqlalchemy.Text)

        # region winners property
        @property
        def winners(self):
            return json.loads(self.winners_raw)

        @winners.setter
        def winners(self, value):
            self.winners_raw = json.dumps(value)
        # endregion

        # region scores property
        @property
        def scores(self):
            return json.loads(self.scores_raw)

        @scores.setter
        def scores(self, value):
            self.scores_raw = json.dumps(value)
        # endregion

        # region settings property
        @property
        def settings(self):
            return json.loads(self.settings_raw)

        @settings.setter
        def settings(self, value):
            self.settings_raw = json.dumps(value)
        # endregion

        # region guesses property
        @property
        def guesses(self):
            return json.loads(self.guesses_raw)

        @guesses.setter
        def guesses(self, value):
            self.guesses_raw = json.dumps(value)
        # endregion

        def __repr__(self):
            return f'<Mailbox game in #{self.channel.last_known_username} with {len(self.winners)} winners>'

        def __init__(self, channel, settings: typing.Dict[str, typing.Union[int, str]], winners,
                     scores: typing.List[int], guesses: typing.List[typing.Dict[str, typing.Union[str, int, list]]]):
            self.channel = channel
            self.settings = settings
            new_winners = []
            for w in winners:
                w2 = w.copy()
                w2['msg'] = str(w2['msg'])
                new_winners.append(w2)

            self.winners = new_winners
            self.scores = scores
            self.guesses = [str(i) for i in guesses]


    return MailboxGame
