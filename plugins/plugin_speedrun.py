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
import typing

import twitchirc

try:
    import main
except ImportError:
    import util_bot as main

    exit()
__meta_data__ = {
    'name': 'plugin_speedrun',
    'commands': [],
}

import srcomapi

api = srcomapi.SpeedrunCom()
current_games: typing.Dict[str, srcomapi.datatypes.Game] = {
    # 'channel': srcomapi.datatypes.Game()
}
current_categories: typing.Dict[str, srcomapi.datatypes.Leaderboard] = {
    # 'channel': srcomapi.datatypes.Leaderboard()
}
current_categories_queries: typing.Dict[str, str] = {

}
current_games_queries: typing.Dict[str, str] = {

}


def _refresh_category(stream_title, channel, picked=None):
    game = current_games[channel]
    fitting = []
    for cat in game.categories:
        print(f'test cat {cat.name!r}, {stream_title!r}')
        if cat.name in stream_title:
            print('cat okay.')
            fitting.append(cat.records[0])
    if len(fitting) > 1:
        if isinstance(picked, int):
            if len(fitting) >= (picked - 1) >= 0:
                current_categories[channel] = fitting[picked - 1]
                current_games_queries[channel] = stream_title+';'+str(picked)
                return True, current_categories[channel].category.name
            return False, 'bad_number'
        elif isinstance(picked, str):
            for i in fitting:
                if i.category.name == picked:
                    current_categories[channel] = i
                    current_games_queries[channel] = stream_title + ';' + str(picked)
                    return True, current_categories[channel].category.name
            for i in fitting:
                if picked in i.category.name:
                    current_categories[channel] = i
                    current_games_queries[channel] = stream_title + ';' + str(picked)
                    return True, current_categories[channel].category.name
        else:
            return False, 'multiple_found'
    elif len(fitting) == 1:
        current_categories[channel] = fitting[0]
        current_games_queries[channel] = stream_title
        return True, fitting[0].category.name
    return False, 'not_found'


def _refresh_game(channel, picked=None):
    stream, ret_code = main.twitch_auth.new_api.get_streams(user_login=channel, wait_for_result=True)
    if ret_code == 200:
        if 'data' in stream:
            if len(stream['data']) == 0:
                return False, 'No stream found.', 'api_no_stream'

            data = stream['data'][0]
            if data['type'] == '':
                return False, f'monkaS {chr(128073)} api error', 'api_other'

            game, ret_code2 = main.twitch_auth.new_api.get_games(id=data['game_id'])
            game = game.json()
            print(game)
            if 'data' in game and len(game['data']):
                # game data in form of
                # {
                #     'data': [
                #         {
                #             'id': 'game id',
                #             'name': 'game name',
                #             'box_art_url': 'url'
                #         }
                #     ]
                # }
                game = game['data'][0]
                res = api.search(srcomapi.datatypes.Game, {'name': game['name']})
                if len(res) > 1:
                    if picked is None or (isinstance(picked, str) and picked.rstrip(' ') == ''):
                        names = ", ".join([i.name for i in res])[::-1].replace(", "[::-1], " and "[::-1], 1)[::-1]
                        # join every games' name with ", " and then replace the last ", " with " and ".

                        return False, f'Found {len(res)} results on sr com. {names}.', 'multiple'

                    if isinstance(picked, int):
                        if picked - 1 > len(res) or picked - 1 < 0:
                            return False, f'Cannot pick game number {picked}.', 'game_bad_id'

                        r: srcomapi.datatypes.Game = res[picked - 1]
                        current_games[channel] = r
                        print('set', r)
                        if channel in current_categories:
                            del current_categories[channel]
                    elif isinstance(picked, str):
                        for i in res:
                            if picked == i.name:
                                current_games[channel] = i
                                if channel in current_categories:
                                    del current_categories[channel]
                                print('set', i)
                                break

                        for i in res:
                            if picked in i.name:
                                current_games[channel] = i
                                if channel in current_categories:
                                    del current_categories[channel]
                                print('set', i)
                                break
                elif len(res) == 1:
                    current_games[channel] = res[0]
                    print('set', res[0])
                else:
                    return False, 'Game not found, weird.', 'game_not_found'
            cat_found, err_name = _refresh_category(data['title'], channel)
            if cat_found:
                return (True, f'{current_games[channel].name} and set category to '
                              f'{current_categories[channel].category.name}',
                        'update_both')
            else:
                return True, f"{current_games[channel].name}, couldn\'t update category: {err_name}", 'update_game'

        else:
            return False, f'monkaS {chr(128073)} API didn\'t return anything.', 'api_empty'

    else:
        return False, f'monkaS {chr(128073)} bad return code {ret_code!r}', 'api_code'


def _format_time(time_):
    minutes = time_ // 60
    seconds = time_ % 60

    hours = minutes // 60
    minutes = minutes % 60
    return (f'{int(hours)} hour{"s" if hours > 1 or hours == 0 else ""}, '
            f'{int(minutes)} minute{"s" if minutes > 1 or minutes == 0 else ""}, '
            f'{int(seconds)} second{"s" if seconds > 1 or seconds == 0 else ""}')


@main.bot.add_command('worldrecord')
def command_worldrecord(msg: twitchirc.ChannelMessage):
    if msg.channel in current_categories:
        category = current_categories[msg.channel]
        time_ = category.runs[0]["run"].times['primary_t']
        players = ' and '.join([p.name for p in category.runs[0]["run"].players])

        main.bot.send(msg.reply(f'@{msg.user} Current WR for {current_games[msg.channel].name} '
                                f'({category.category.name}) is '
                                f'{_format_time(time_)} by {players}'))
    else:
        if msg.channel in current_games:
            main.bot.send(msg.reply(f'@{msg.user}, There is a game set but there is no category set. Cannot fetch WR.'))
        else:
            main.bot.send(msg.reply(f'@{msg.user}, There is no game set on this channel. Ask a mod to run the '
                                    f'update_game command.'))


@main.bot.add_command('update_game', forced_prefix=None, enable_local_bypass=True,
                      required_permissions=['wr.update_game'])
def command_update_game(msg: twitchirc.ChannelMessage):
    picked = (msg.text + ' ').split(' ', 1)[1].rstrip(' ')

    if picked == '':
        picked = None
    elif picked.isnumeric():
        picked = int(picked)

    st, ret_msg, err_name = _refresh_game(msg.channel, picked=picked)
    if st is False:
        if err_name == 'multiple':
            main.bot.send(msg.reply(f'@{msg.user} {ret_msg}. Use {command_update_game.chat_command} [number] '
                                    f'or {command_update_game.chat_command} [game title]'
                                    f'or {command_update_game.chat_command} [part of title] to select the game.'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} Error: {ret_msg}'))
    else:
        main.bot.send(msg.reply(f'@{msg.user}, Okay, set game to {ret_msg}'))


@main.bot.add_command('update_cat', forced_prefix=None, enable_local_bypass=True,
                      required_permissions=['wr.update_cat'])
def command_update_cat(msg: twitchirc.ChannelMessage):
    if msg.channel not in current_games:
        main.bot.send(msg.reply(f'@{msg.user} Cannot update category, there\'s no game set.'))
        return
    picked = (msg.text + ' ').split(' ', 1)[1].rstrip(' ')

    if picked == '':
        picked = None
    elif picked.isnumeric():
        picked = int(picked)
    if picked is None:
        stream, ret_code = main.twitch_auth.new_api.get_streams(user_login=msg.channel, wait_for_result=True)
        if ret_code == 200:
            if 'data' in stream:
                data = stream['data'][0]
                if data['type'] == '':
                    main.bot.send(msg.reply(f'@{msg.user} monkaS {chr(127073)} API error.'))
                    return
                o, err_name = _refresh_category(stream['title'], msg.channel, picked)
                if o:
                    main.bot.send(msg.reply(f'@{msg.user} Okay, set category to {picked}'))
                else:
                    main.bot.send(msg.reply(f'@{msg.user} monkaS Something didn\'t work out.'))
            else:
                main.bot.send(msg.reply(f'@{msg.user} Stream not found.'))
    else:
        cat_name, filter_ = picked.split(';', 1)
        if filter_ == '':
            filter_ = None
        elif filter_.isnumeric():
            filter_ = int(filter_)
        o, name = _refresh_category(cat_name, msg.channel, filter_)
        if o:
            main.bot.send(msg.reply(f'@{msg.user} Okay, set category to {picked}'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} monkaS Something didn\'t work out. ({name})'))
