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
import math
import re
import time
import traceback
import typing

from plugins.models import mailbox_game

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
GUESS_PATTERN = re.compile(r'^(\d{1,2}) (\d{1,2}) (\d{1,2})(?: \U000e0000)?$')


class Plugin(main.Plugin):
    no_reload = True
    name = NAME
    commands: typing.List[str] = ['mailbox', 'mailgame']

    def __init__(self, module, source):
        super().__init__(module, source)
        self.MailboxGame = mailbox_game.get(main.Base)
        self.game_enabled_setting = plugin_manager.Setting(
            self,
            'mailbox_game.enabled',
            default_value=False,
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True,
            on_load=self._load_from_settings,
            help_='Toggles whether or not the mailbox guessing game is enabled in the channel.'
        )

        self.after_game_timeout_length = plugin_manager.Setting(
            self,
            'mailbox_game.timeout_after',
            default_value=-1,
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True,
            help_='Sets how big is the timeout for guessing after the mail minigame has stopped accepting guesses.'
        )

        self.after_game_timeout_message = plugin_manager.Setting(
            self,
            'mailbox_game.timeout_message',
            default_value='Your guess was late. To prevent spam you have been timed out.',
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True,
            help_='Sets the timeout message for timeouts after the mail minigame has stopped accepting guesses.'
        )
        self.mailbox_games = {}
        self.command_mailbox = main.bot.add_command('mailbox', limit_to_channels=[], available_in_whispers=False,
                                                    required_permissions=['mailbox.manage'],
                                                    enable_local_bypass=True)(self.command_mailbox)
        self.command_mailbox.aliases.append('mailgame')

        self.command_delete_guesses_after_stop = main.bot.add_command(
            '[plugin_mailboxgame:remove_guesses_after_stop]',
            available_in_whispers=False,
            cooldown=main.CommandCooldown(0, 0, 0, True)  # no cooldowns,
        )(self.command_delete_guesses_after_stop)
        self.command_delete_guesses_after_stop.limit_to_channels = []
        self.command_delete_guesses_after_stop.matcher_function = self._delete_guesses_matcher

        main.reloadables['mailbox_channels'] = self._reload_channels

        plugin_help.create_topic('mailbox', 'Manage the mailbox game. Subcommands: mailbox start, '
                                            'mailbox stop, mailbox draw.', section=plugin_help.SECTION_COMMANDS)

        plugin_help.create_topic('mailbox stop',
                                 'Stop accepting new guesses into the minigame',
                                 section=plugin_help.SECTION_ARGS)

        plugin_help.create_topic('mailbox draw',
                                 'Draw winner(s) of the minigame. Syntax: mailbox draw NN NN NN, '
                                 'where NN is a number, numbers need to be separated by spaces, '
                                 'they don\'t need leading zeros',
                                 section=plugin_help.SECTION_ARGS)

        plugin_help.create_topic('mailbox start',
                                 'Start the mailbox minigame. Possible arguments are guesses, '
                                 'plebs, subs, mods, vips, '
                                 'find_best, winners. Help for these is at "mailbox start ARGUMENT"',
                                 section=plugin_help.SECTION_ARGS)

        plugin_help.create_topic('mailbox start plebs',
                                 'Should plebs (non-subs) be allowed to guess, Use -plebs to disallow plebs to guess. '
                                 'Default: true',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('mailbox start guesses',
                                 'How many guesses should people have. Use guesses:NUMBER to change. Default: 1.',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('mailbox start subs',
                                 'Should subs be allowed to guess. Use -subs to disallow subs to guess. '
                                 'Broadcaster can vote if this argument or the mods argument is true. Default: true',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('mailbox start mods',
                                 'Should mods be allowed to guess. Use -mods to disallow mods to guess. '
                                 'Broadcaster can vote if this argument or the subs argument is true. Default: true',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('mailbox start vips',
                                 'Should vip be allowed to guess. Use -vips to disallow vips to guess. Default: true',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('mailbox start find_best',
                                 'Should the best matches be shown. If false only shows full matches. '
                                 'Use -find_best to disable that behaviour. Default: true',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('mailbox start winners',
                                 'Highest amount of names shown when drawing winner(s). Full natches are always shown. '
                                 'Use winners:NUMBER to change this number. Default: 3',
                                 section=plugin_help.SECTION_ARGS)
        plugin_help.create_topic('mailbox start punish_more',
                                 'Punish users for guessing more than they are allowed to. '
                                 'This will make the users guesses worth zero points. '
                                 'Use -punish_more to disable this. Default: true',
                                 section=plugin_help.SECTION_ARGS)

    def _reload_channels(self):
        self.command_mailbox.limit_to_channels = []
        for channel, settings in plugin_manager.channel_settings.items():
            settings: plugin_manager.ChannelSettings
            if settings.get(self.game_enabled_setting):
                self.command_mailbox.limit_to_channels.append(channel)
        self.command_mailbox_alias.limit_to_channels = self.command_mailbox.limit_to_channels
        return len(self.command_mailbox.limit_to_channels)

    def _load_from_settings(self, channel_settings: plugin_manager.ChannelSettings):
        is_enabled = channel_settings.get(self.game_enabled_setting)
        username = channel_settings.channel.last_known_username
        if is_enabled:
            if username not in self.command_mailbox.limit_to_channels:
                self.command_mailbox.limit_to_channels.append(username)
                self.command_delete_guesses_after_stop.limit_to_channels.append(username)
        else:
            if username in self.command_mailbox.limit_to_channels:
                self.command_mailbox.limit_to_channels.remove(username)
                self.command_delete_guesses_after_stop.limit_to_channels.remove(username)

    # region delete extraneous guesses
    def _delete_guesses_matcher(self, msg: main.StandardizedMessage, _):
        return bool(GUESS_PATTERN.match(msg.text))

    async def command_delete_guesses_after_stop(self, msg: main.StandardizedMessage):
        game = self.mailbox_games.get(msg.channel)
        if not game:
            return None  # don't return any message as this 'command' triggers on any message

        if game.get('end_time'):
            to_len = plugin_manager.channel_settings[msg.channel].get(self.after_game_timeout_length)
            to_msg = plugin_manager.channel_settings[msg.channel].get(self.after_game_timeout_message)
            if to_len >= 0:
                # make sure to send the timeout properly

                if to_len == 0:
                    send_msg = msg.moderate().format_delete()
                else:
                    send_msg = msg.moderate().format_timeout(
                        str(to_len) + 's',
                        to_msg
                    )

                # bypass rate-limitting
                main.bot.clients[main.Platform.TWITCH].connection.force_send(send_msg)

    # endregion

    # region _mailgame/_mailbox
    def _nice_minigame_settings(self, settings: typing.Dict[str, typing.Union[int, bool]]):
        can_take_part = []
        for i in ('plebs', 'subs', 'mods', 'vips'):
            if settings[i] is True:
                can_take_part.append(i)

        output = f'Number of guesses is {settings["guesses"]}, {", ".join(can_take_part)} can take part'

        return output

    def command_mailbox(self, msg: twitchirc.ChannelMessage):
        argv = main.delete_spammer_chrs(msg.text).rstrip(' ').split(' ', 2)
        if len(argv) == 1:
            return plugin_help.find_topic('mailbox') + ' For full help see the help command.'
        action = argv[1]
        if action == 'start':
            return self._mailbox_start(argv, msg)
        elif action == 'draw':
            return self._mailbox_draw(argv, msg)
        elif action == 'stop':
            return self._mailbox_stop(msg)
        else:
            return f'@{msg.user}, Unknown action: {action!r}'

    # region mailbox subcommands
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
                'find_best': bool,
                'punish_more': bool
            }, strict_escapes=False, strict_quotes=True, ignore_arg_zero=False)
        except arg_parser.ParserError as e:
            return f'@{msg.user}, Unexpected error when processing arguments: {e.message}'
        if msg.channel in self.mailbox_games:
            return (f'@{msg.user}, Game is already running in this channel. '
                    f'If you want to override the game use "{argv[0]} stop", then "{msg.text}"')
        if action_args['guesses'] is ...:
            action_args['guesses'] = 1

        if action_args['punish_more'] is ...:
            action_args['punish_more'] = True

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
        return f'Minigame starts now! Settings: {self._nice_minigame_settings(action_args)}'

    def _mailbox_draw(self, argv, msg):
        if msg.channel not in self.mailbox_games:
            return f'@{msg.user}, Cannot draw a winner from mailbox minigame, there is none running. FeelsBadMan'
        settings = self.mailbox_games[msg.channel]
        action_argv = ' '.join(argv[2:])

        show_closed = False
        if 'end_time' not in settings:
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

        possible_guesses = list(self._filter_messages(msgs, settings))

        print('possible', possible_guesses)
        good_guesses = self._find_good_guesses(possible_guesses, good_value, settings)
        print('good', good_guesses)
        best = self._best_guess(settings, good_guesses)
        print('best', best)
        print(settings)
        save_start_time = time.monotonic()
        failed_save = False

        # noinspection PyBroadException
        try:
            with main.session_scope() as session:
                game_obj = self.MailboxGame(main.User.get_by_twitch_id(int(msg.flags['room-id']), session),
                                            settings, best.copy(), good_value, possible_guesses)
                session.add(game_obj)
        except Exception:
            failed_save = True
            traceback.print_exc()
        save_end_time = time.monotonic()

        del self.mailbox_games[msg.channel]
        db_notif = (
            f'{"Failed to save to database." if failed_save else "Saved winners to database."} '
            f'Time taken: {save_end_time - save_start_time:.2f}s. ID: {game_obj.id if not failed_save else "n/a"}'
        )
        if len(best) == 0:
            return (f'{"(automatically closed the game)" if show_closed else ""}'
                    f'No one guessed {"even remotely " if settings["find_best"] else ""}right. {db_notif}')

        else:
            message = (f'{"(automatically closed the game)" if show_closed else ""}'
                       f'Best guesses are {self._nice_best_guesses(best)}. {db_notif}')
            if len(message) > 500:
                msgs = []
                for i in range(1, math.ceil(len(message) / 500) + 1):
                    msgs.append(message[(i - 1) * 500:i * 500])
                return msgs
            return message

    def _mailbox_stop(self, msg):
        if msg.channel not in self.mailbox_games:
            return f'@{msg.user}, Cannot stop the mailbox minigame, there is none running. FeelsBadMan'
        else:
            game = self.mailbox_games[msg.channel]
            if 'end_time' not in game:
                game['end_time'] = time.time()
                return 'Entries are now closed!'
            else:
                return (f'@{msg.user}, This game has closed '
                        f'({datetime.timedelta(seconds=round(time.time() - game["end_time"]))} ago). ')

    # endregion

    # region mailbox draw helpers
    def _filter_messages(self, msgs, settings):
        def filter_function(m: twitchirc.ChannelMessage):
            grp = twitchirc.auto_group(m)
            if grp == 'default':
                return settings['plebs']
            elif grp == 'broadcaster':
                return settings['subs'] or settings['mods']
            elif grp == 'subscriber':
                return settings['subs']
            elif grp in ('moderator', 'staff'):
                return settings['mods']
            else:
                return False

        first_parse = filter(filter_function, msgs)
        # all of the messages by users not included in the minigame should be gone now.

        possible_guesses = filter(lambda m: bool(GUESS_PATTERN.match(m.text)), first_parse)
        return possible_guesses

    def _best_guess(self, settings,
                    good_guesses: typing.Dict[str, typing.Dict[str, typing.Union[int, twitchirc.ChannelMessage]]]):
        best = []
        for num, guess in enumerate(sorted(good_guesses.values(), key=lambda o: o['quality'], reverse=True)):
            if num > settings['winners'] and guess['quality'] != 3:  # always display all winners
                break

            if not settings['find_best'] and guess['quality'] < 3:  # not trying to find best, just the exact
                break

            if guess['quality'] == 0:
                break

            best.append(guess)
        return best

    def _find_good_guesses(self, guesses: typing.List[twitchirc.ChannelMessage], good, settings):
        good_guesses: typing.Dict[str, typing.Dict[str, typing.Union[int, twitchirc.ChannelMessage,
                                                                     typing.List[int]]]] = {
            # 'user': {
            #     'msg': twitchirc.ChannelMessage(),
            #     'quality': 3 # guess quality, 0/3 no match, 3/3 full match
            #     'parsed': [1, 2, 3],
            #     'count': 1
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
                if guess != good_guesses[i.user]['parsed']:
                    good_guesses[i.user]['count'] += 1

                if good_guesses[i.user]['count'] > settings['guesses']:
                    if settings['punish_more']:
                        good_guesses[i.user]['quality'] = 0
                    continue  # ignore any further guesses.
                if good_guesses[i.user]['quality'] < points:
                    good_guesses[i.user]['quality'] = points
                    good_guesses[i.user]['msg'] = i
                    good_guesses[i.user]['parsed'] = guess
            else:
                good_guesses[i.user] = {
                    'quality': points,
                    'msg': i,
                    'parsed': guess,
                    'count': 1
                }

        return good_guesses

    def _nice_best_guesses(self, best):
        output = []
        for i in best:
            is_sub = any([i.startswith('subscriber') for i in i['msg'].flags['badges']])
            output.append(f'@{i["msg"].user} {"(Sub)" if is_sub else ""} ({i["quality"]}/3)')
        return ', '.join(output)
    # endregion
    # endregion
