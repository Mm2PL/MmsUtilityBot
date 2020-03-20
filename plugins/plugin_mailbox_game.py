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
import re
import time
import typing

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()

try:
    # noinspection PyPackageRequirements
    import plugin_plugin_manager as plugin_manager

except ImportError:
    if typing.TYPE_CHECKING:
        import plugins.plugin_manager as plugin_manager
    else:
        raise

main.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    if typing.TYPE_CHECKING:
        import plugins.plugin_help as plugin_help
    else:
        raise

main.load_file('plugins/plugin_chat_cache.py')
try:
    import plugin_chat_cache
except ImportError:
    if typing.TYPE_CHECKING:
        from plugins.plugin_chat_cache import Plugin as PluginChatCache

        plugin_chat_cache: PluginChatCache
    else:
        raise

import twitchirc
import plugins.utils.arg_parser as arg_parser

NAME = 'mailbox_game'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
log = main.make_log_function(NAME)
GUESS_PATTERN = re.compile(r'(\d{1,2}[,-]? ?)(\d{1,2}[,-]? ?)(\d{1,2}[,-]? ?)')


class Plugin(main.Plugin):
    commands: typing.List[str] = ['mailbox']

    def __init__(self, module, source):
        super().__init__(module, source)
        self.game_enabled_setting = plugin_manager.Setting(
            self,
            'mailbox_game.enabled',
            default_value=False,
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True
        )
        self.mailbox_games = {}
        self.command_mailbox = main.bot.add_command('mailbox', limit_to_channels=[], available_in_whispers=False,
                                                    required_permissions=['mailbox.manage'],
                                                    enable_local_bypass=True)(self.command_mailbox)
        main.reloadables['mailbox_channels'] = self._reload_channels
        main.bot.schedule_event(0.1, 10, self._reload_channels, (), {})  # load channels

    def _reload_channels(self):
        self.command_mailbox.limit_to_channels = []
        for channel, settings in plugin_manager.channel_settings.items():
            settings: plugin_manager.ChannelSettings
            if settings.get(self.game_enabled_setting):
                self.command_mailbox.limit_to_channels.append(channel)
        return len(self.command_mailbox.limit_to_channels)

    @property
    def no_reload(self):
        return True

    @property
    def name(self) -> str:
        return NAME

    def _nice_minigame_settings(self, settings: typing.Dict[str, typing.Union[int, bool]]):
        can_take_part = []
        for i in ('plebs', 'subs', 'mods', 'vips'):
            if settings[i] is True:
                can_take_part.append(i)

        output = f'Number of guesses is {settings["guesses"]}, {", ".join(can_take_part)} can take part'

        return output

    def command_mailbox(self, msg: twitchirc.ChannelMessage):
        argv = msg.text.split(' ', 2)
        if len(argv) == 1:
            return plugin_help.find_topic('mailbox')
        action = argv[1]
        if action == 'start':
            return self._mailbox_start(argv, msg)
        elif action == 'draw':
            return self._mailbox_draw(argv, msg)
        elif action == 'stop':
            return self._mailbox_stop(msg)
        else:
            return f'@{msg.user}, Unknown action: {action!r}'

    def _mailbox_start(self, argv, msg):
        action_argv = ' '.join(argv[2:])
        try:
            action_args = arg_parser.parse_args(action_argv, {
                'guesses': int,
                'plebs': bool,
                'subs': bool,
                'mods': bool,
                'vips': bool,
                'winners': int,
                'find_best': bool
            }, strict_escapes=False, strict_quotes=True, ignore_arg_zero=False)
        except arg_parser.ParserError as e:
            return f'@{msg.user}, Unexpected error when processing arguments: {e.message}'

        if action_args['guesses'] is ...:
            action_args['guesses'] = 1

        if action_args['guesses'] < 1:
            return f'@{msg.user}, Number of guesses cannot be less than one.'

        if action_args['find_best'] is ...:
            action_args['find_best'] = True  # only search for exact best.
        if action_args['winners'] is ...:
            action_args['winners'] = 3  # only search for exact best.

        for i in ('plebs', 'subs', 'mods', 'vips'):
            if action_args[i] is ...:
                action_args[i] = True
        if sum([action_args[i] for i in ('plebs', 'subs', 'mods', 'vips')]) == 0:
            return f'@{msg.user}, Nobody can take part in this mailbox minigame. ' \
                   f'why bother with it then? FeelsBadMan'
        action_args['start_time'] = time.time()
        self.mailbox_games[msg.channel] = action_args
        action_args['old_cache_length'] = plugin_chat_cache.max_cache_length[msg.channel]
        plugin_chat_cache.max_cache_length[msg.channel] *= 10
        return f'Minigame starts now! Settings: {self._nice_minigame_settings(action_args)}'

    def _mailbox_draw(self, argv, msg):
        if msg.channel not in self.mailbox_games:
            return f'@{msg.user}, Cannot draw a winner from mailbox minigame, there is none running. FeelsBadMan'
        settings = self.mailbox_games[msg.channel]
        action_argv = ' '.join(argv[2:])

        show_closed = False
        if 'end_time' not in settings:
            plugin_chat_cache.max_cache_length[msg.channel] = settings['old_cache_length']
            settings['end_time'] = time.time()
            show_closed = True

        match = GUESS_PATTERN.match(action_argv)
        if not match:
            return (f'@{msg.user}, Bad winning value, should be in format of "00-99 00-99 00-99" '
                    f'(/{GUESS_PATTERN.pattern}/).'
                    f'{" The game has been automatically closed." if show_closed else ""}')

        good_value = [int(i.rstrip(', -')) for i in match.groups()]

        msgs = plugin_chat_cache.find_messages(msg.channel, min_timestamp=settings['start_time'],
                                               max_timestamp=settings['end_time'])

        possible_guesses = self._filter_messages(msgs, settings)

        guesses = self._count_guesses(possible_guesses, settings)
        good_guesses = self._find_good_guesses(guesses, good_value)
        best = self._best_guess(settings, good_guesses)
        del self.mailbox_games[msg.channel]
        if len(best) == 0:
            return (f'{"(automatically closed the game)" if show_closed else ""}'
                    f'No one guessed {"even remotely " if settings["find_best"] else ""}right')
        else:
            return (f'{"(automatically closed the game)" if show_closed else ""}'
                    f'Best guesses are {self._nice_best_guesses(best)}')

    def _filter_messages(self, msgs, settings):
        def _(m: twitchirc.ChannelMessage):
            grp = twitchirc.auto_group(m)
            if grp == 'default':
                return settings['plebs']
            elif grp == 'broadcaster':
                return settings['subs'] or settings['mods']
            elif grp in 'subscriber':
                return settings['subs']
            elif grp == ('moderator', 'staff'):
                return settings['mods']
            else:
                return False

        first_parse = filter(_, msgs)  # all of the messages by users not included in the minigame should be gone now.
        del _

        def _(m: twitchirc.ChannelMessage):
            return bool(GUESS_PATTERN.match(m.text))

        possible_guesses = filter(_, first_parse)
        del _
        return possible_guesses

    def _best_guess(self, settings,
                    good_guesses: typing.Dict[str, typing.Dict[str, typing.Union[int, twitchirc.ChannelMessage]]]):
        best = []
        for num, guess in enumerate(sorted(good_guesses.values(), key=lambda o: o['quality'])):
            if num > settings['winners']:
                break

            if not settings['find_best'] and guess['quality'] < 3:  # not trying to find best, just the exact
                break

            if guess['quality'] == 0:
                break

            best.append(guess)
        return best

    def _find_good_guesses(self, guesses: typing.List[twitchirc.ChannelMessage], good):
        good_guesses: typing.Dict[str, typing.Dict[str, typing.Union[int, twitchirc.ChannelMessage]]] = {
            # 'user': {
            #     'msg': twitchirc.ChannelMessage(),
            #     'quality': 3 # guess quality, 0/3 no match, 3/3 full match
            # }
        }
        for i in guesses:
            match = GUESS_PATTERN.match(i.text)
            guess = [int(i.rstrip(', -')) for i in match.groups()]
            points = 0
            for num, g in enumerate(guess):
                if g == good[num]:
                    points += 1

            if i.user in good_guesses:  # check if user had a better guess before
                if good_guesses[i.user]['quality'] < points:
                    good_guesses[i.user]['quality'] = points
                    good_guesses[i.user]['msg'] = i
            else:
                good_guesses[i.user] = {
                    'quality': points,
                    'msg': i
                }

        return good_guesses

    def _count_guesses(self, first_parse, settings):
        number_guesses = {}
        guesses = []

        for message in first_parse:
            if message.user not in number_guesses:
                number_guesses[message.user] = 0
            number_guesses[message.user] += 1
            guesses.append(message)

        for user, amount in number_guesses.items():
            if amount > settings['guesses']:
                for i in guesses.copy():
                    if i.user == user:
                        guesses.remove(i)

        print(guesses, number_guesses)
        return guesses

    def _nice_best_guesses(self, best):
        output = []
        for i in best:
            output.append(f'{i["msg"].user} ({i["quality"]}/3)')
        return ', '.join(output)

    def _mailbox_stop(self, msg):
        if msg.channel not in self.mailbox_games:
            return f'@{msg.user}, Cannot stop the mailbox minigame, there is none running. FeelsBadMan'
        else:
            game = self.mailbox_games[msg.channel]
            plugin_chat_cache.max_cache_length[msg.channel] = game['old_cache_length']
            if 'end_time' not in game:
                game['end_time'] = time.time()
                return 'Entries are now closed!'
            else:
                return (f'@{msg.user}, This game has closed '
                        f'{datetime.timedelta(seconds=round(time.time() - game["end_time"]))} ago.')
