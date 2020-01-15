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
import sqlalchemy
from flask import abort, jsonify
from sqlalchemy import text

try:
    from plugins.models import suggestion as suggestion_model

    # for static analysis
except ImportError:
    pass


def init(register_endpoint, ipc_conn, main_module):
    suggestion_model = main_module.load_model('suggestion')
    Suggestion = suggestion_model.get(main_module.Base)

    @register_endpoint('/suggestions/list/user/<int:user_id>/<int:page>')
    def list_suggestions(user_id: int, page: int):
        """
        List suggestions filtering by user.

        :param user_id: Twitch uid of the user you want to search for.
        :param page: Page number you want. Pages are 50 or less entries in size, indexed from 0.

        .. start-raw
        <ol>
            <li>
                <b>page (Number)</b> page number you are on.
            </li>
            <li>
                <b>page_size (Number)</b> maximum size of a page.
            </li>
            <li>
                <b>count (Number)</b> total number of suggestions.
            </li>
            <li>
                <b>data (Object[])</b> data
                <ul>
                    <li>
                        <b>text (String)</b> text of the suggestion
                    </li>
                    <li>
                        <b>notes (String)</b> notes from the suggestion
                    </li>
                    <li>
                        <b>state (String)</b> suggestion state, can be 'new', 'not_a_suggestion', 'rejected', 'accepted'
                    </li>
                    <li>
                        <b>creation_date (String)</b> ISO representation of the date,
                        format string used is "%Y-%m-%dT%H:%M%SZ"
                    </li>
                </ul>
            </li>
        </ol>
        .. stop-raw
        """
        with main_module.session_scope() as session:
            user: main_module.User = (session.query(main_module.User).filter(main_module.User.twitch_id == user_id)
                                      .first())
            if user is None:
                r = jsonify({
                    'status': 200,
                    'page': page,
                    'page_size': main_module.PAGE_SIZE,
                    'count': 0,
                    'data': []
                })
                return r

            suggestion_query = (session.query(Suggestion)
                                .filter(Suggestion.author_alias == user.id)
                                .filter(Suggestion.is_hidden == False))
            count = suggestion_query.count()
            suggestions = (suggestion_query.offset(page * main_module.PAGE_SIZE)
                           .limit(main_module.PAGE_SIZE)
                           .all())
        return jsonify({
            'status': 200,
            'page': page,
            'page_size': main_module.PAGE_SIZE,
            'count': count,
            'data': [
                {
                    'text': suggestion.text,
                    'notes': suggestion.notes,
                    'state': suggestion.state.name,
                    'id': suggestion.id,
                    'creation_date': (suggestion.creation_date.strftime("%Y-%m-%dT%H:%M%SZ")
                                      if suggestion.creation_date is not None else None),
                }
                for suggestion in suggestions
            ]

        })

    @register_endpoint('/suggestions/list/<int:page>')
    def list_all_suggestions(page):
        """
        List suggestions

        :param page: Page number you want. Pages are 50 or less entries in size, indexed from 0.

        .. start-raw
        <h3>Returns</h3>
        <ol>
            <li>
                <b>page (Number)</b> page number you are on.
            </li>
            <li>
                <b>page_size (Number)</b> maximum size of a page.
            </li>
            <li>
                <b>count (Number)</b> total number of suggestions.
            </li>
            <li>
                <b>data (Object[])</b> data
                <ul>
                    <li>
                        <b>text (String)</b> text of the suggestion
                    </li>
                    <li>
                        <b>notes (String)</b> notes from the suggestion
                    </li>
                    <li>
                        <b>state (String)</b> suggestion state, can be 'new', 'not_a_suggestion', 'rejected', 'accepted'
                    </li>
                    <li>
                        <b>creation_date (String)</b> ISO representation of the date,
                        format string used is "%Y-%m-%dT%H:%M%SZ"
                    </li>
                    <li>
                        <b>author (Object)</b> object representing the author of the suggestion
                        <ul>
                            <li>
                                <b>id</b> Twitch user id of the account
                            </li>
                            <li>
                                <b>name</b> Last known user name of this account.
                            </li>
                        </ul>
                    </li>
                </ul>
            </li>
        </ol>
        .. stop-raw
        """
        with main_module.session_scope() as session:
            suggestion_query = (session.query(Suggestion)
                                .filter(Suggestion.is_hidden == False))
            count = suggestion_query.count()
            suggestions = (suggestion_query.offset(page * main_module.PAGE_SIZE)
                           .limit(main_module.PAGE_SIZE)
                           .all())
            return jsonify({
                'status': 200,
                'page': page,
                'page_size': main_module.PAGE_SIZE,
                'count': count,
                'data': [
                    {
                        'text': suggestion.text,
                        'notes': suggestion.notes,
                        'state': suggestion.state.name,
                        'id': suggestion.id,
                        'creation_date': (suggestion.creation_date.strftime("%Y-%m-%dT%H:%M%SZ")
                                          if suggestion.creation_date is not None else None),
                        'author': {
                            'id': suggestion.author.twitch_id,
                            'name': suggestion.author.last_known_username
                        }
                    }
                    for suggestion in suggestions
                ]

            })

    @register_endpoint('/suggestions/stats')
    def stats():
        """
        Show statistics of suggestions.

        .. start-raw
        <h3>Returns</h3>
        <ol>
            <li>
                <b>count (Number)</b> Number of suggestions
            </li>
            <li>
                <b>count_hidden (Number)</b> Number of hidden suggestions
            </li>
            <li>
                <b>states (Object)</b>
                STATE_NAME = COUNT
            </li>
            <li>
                <b>top_users (Object[])</b>
                <ul>
                    <li>
                        id<br>
                        Type: int<br>
                        Twitch ID of the person
                    </li>
                    <li>
                        count<br>
                        Type: int<br>
                        Number of this person's suggestions
                    </li>
                    <li>
                        name<br>
                        Type: String<br>
                        Last known username of this person.
                    </li>
                </ul>
            </li>
        </ol>
        .. stop-raw
        """
        with main_module.session_scope() as session:
            return jsonify({
                'status': 200,
                'count': session.query(Suggestion).count(),
                'count_hidden': session.query(Suggestion).filter(Suggestion.is_hidden == True).count(),
                'states': {
                    i[0].name: i[1] for i in (session.query(Suggestion.state, sqlalchemy.func.count())
                                              .group_by(Suggestion.state).all())
                },
                'top_users': [
                    {
                        'id': i[2].twitch_id,
                        'count': i[1],
                        'name': i[2].last_known_username
                    }
                    for i in (
                        session.query(Suggestion.author_alias, sqlalchemy.func.count(), main_module.User)
                            .group_by(Suggestion.author_alias)
                            .order_by(sqlalchemy.desc(text('count_1')))
                            .join(main_module.User)
                            .limit(10)
                            .all()
                    )
                ]
            })
