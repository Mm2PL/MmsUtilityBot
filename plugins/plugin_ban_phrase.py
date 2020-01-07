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
import typing

import twitchirc
from twitchirc import Event

try:
    import regex as re
except ImportError:
    print('Unable to import regex, using re instead.')
    import re

try:
    # noinspection PyUnresolvedReferences
    import main
except ImportError:
    import util_bot as main

    exit(1)
import plugins.models.banphrase as banphrase_model

NAME = 'ban_phrase'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': []
}
log = main.make_log_function(NAME)
BanPhraseType = banphrase_model.BanPhraseType
BanPhrase = banphrase_model.get(main.Base, log, main.session_scope, main.User)
ban_phrases: typing.List[BanPhrase] = []


class BanPhraseMiddleware(twitchirc.AbstractMiddleware):
    def send(self, event: Event) -> None:
        msg: twitchirc.ChannelMessage = event.data.get('message')
        if isinstance(msg, twitchirc.ChannelMessage):
            text = msg.text

            for phrase in ban_phrases:
                if phrase.channel_alias is None or phrase.channel.last_known_username == msg.channel:
                    if not phrase.output:
                        continue
                    text = phrase.check_and_replace(text)
                    if text is None:
                        event.cancel()
                        return
            msg.text = text

    def receive(self, event: Event) -> None:
        msg: twitchirc.ChannelMessage = event.data.get('message')
        if isinstance(msg, twitchirc.ChannelMessage):
            text = msg.text

            for phrase in ban_phrases:
                if phrase.channel_alias is None or phrase.channel.last_known_username == msg.channel:
                    if not phrase.input:
                        continue

                    text = phrase.check_and_replace(text)
                    if phrase.type == BanPhraseType.deny and phrase.check(text):
                        event.cancel()
                        event.source.send(msg.reply(phrase.warning))
                        return
                    if text is None:
                        event.cancel()
                        return
            msg.text = text

    def command(self, event: Event) -> None:
        pass

    def permission_check(self, event: Event) -> None:
        pass

    def join(self, event: Event) -> None:
        pass

    def part(self, event: Event) -> None:
        pass

    def disconnect(self, event: Event) -> None:
        pass

    def connect(self, event: Event) -> None:
        pass

    def add_command(self, event: Event) -> None:
        pass


main.bot.middleware.append(BanPhraseMiddleware())

ban_phrase_read_only_session = None


def _init():
    global ban_phrase_read_only_session

    ban_phrase_read_only_session = main.Session()
    ban_phrase_read_only_session.flush = lambda *a, **kw: print('BP: Flushing a readonly session.')
    print('Load ban phrases.')
    for i in BanPhrase.load_all(ban_phrase_read_only_session):
        ban_phrases.append(i)
    print(f'Done. Loaded {len(ban_phrases)} ban phrases.')


main.bot.schedule_event(0.1, 100, _init, (), {})


def _reload_ban_phrases():
    global ban_phrases, ban_phrase_read_only_session
    ban_phrases = []
    ban_phrase_read_only_session.close()
    _init()
    return 'Done.'


main.reloadables['ban_phrases'] = _reload_ban_phrases
