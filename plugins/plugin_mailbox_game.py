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

import sqlalchemy.exc

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
        self.default_no_game_timeout_reason = plugin_manager.Setting(
            self,
            'mailbox_game.no_game_timeout_message',
            default_value='There is no mail minigame running. Please don\'t spam.',
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True,
            help_='Sets the timeout message for semi-manual timeouts. See help for "mailgame timeout"'
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
                                            'mailbox stop, mailbox draw, mailbox cancel.',
                                 section=plugin_help.SECTION_COMMANDS,
                                 links=[
                                     'mailgame'
                                 ])

        plugin_help.create_topic('mailbox stop',
                                 'Stop accepting new guesses into the minigame. This subcommand takes no arguments.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame stop'
                                 ])

        plugin_help.create_topic('mailbox draw',
                                 'Draw winner(s) of the minigame. Syntax: mailbox draw NN NN NN, '
                                 'where NN is a number, numbers need to be separated by spaces, '
                                 'they don\'t need leading zeros',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame draw'
                                 ])

        plugin_help.create_topic('mailbox start',
                                 'Start the mailbox minigame. Possible arguments are guesses, '
                                 'find_best, winners. Help for these is at "mailbox start ARGUMENT_NAME"',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame start'
                                 ])
        plugin_help.create_topic('mailbox cancel',
                                 'Cancels the ongoing mailbox minigame. This subcommand takes no arguments.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame cancel'
                                 ])
        plugin_help.create_topic('mailbox timeout',
                                 'Sets up manual timeouts for guesses. This subcommand takes one optional argument: '
                                 'the timeout reason, a multi-word string.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame timeout'
                                 ])

        plugin_help.create_topic('mailbox start guesses',
                                 'How many guesses should people have. Use guesses:NUMBER to change. Default: 1.',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame start guesses'
                                 ])
        plugin_help.create_topic('mailbox start find_best',
                                 'Should the best matches be shown. If false only shows full matches. '
                                 'Use -find_best to disable that behaviour. Default: true',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame start find_best'
                                 ])
        plugin_help.create_topic('mailbox start winners',
                                 'Highest amount of names shown when drawing winner(s). Full natches are always shown. '
                                 'Use winners:NUMBER to change this number. Default: 3',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame start winners'
                                 ])
        plugin_help.create_topic('mailbox start punish_more',
                                 'Punish users for guessing more than they are allowed to. '
                                 'This will make the users guesses worth zero points. '
                                 'Use -punish_more to disable this. If disabled the first guess will be used. '
                                 'Duplicating the same guess will never cause disqualification. '
                                 'Default: true',
                                 section=plugin_help.SECTION_ARGS,
                                 links=[
                                     'mailgame start punish_more'
                                 ])

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
            to_msg = (
                    game.get('timeout_reason')
                    or plugin_manager.channel_settings[msg.channel].get(self.after_game_timeout_message)
            )
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

    def command_mailbox(self, msg: main.StandardizedMessage):
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
        elif action == 'cancel':
            return self._mailbox_cancel(msg)
        elif action == 'timeout':
            return self._mailbox_timeout(argv, msg)
        elif action == 'whatif':
            return self._mailbox_whatif(argv, msg)
        else:
            return f'@{msg.user}, Unknown action: {action!r}'

    # region mailbox subcommands
    def _mailbox_start(self, argv, msg):
        action_argv = ' '.join(argv[2:])
        try:
            action_args = arg_parser.parse_args(
                action_argv,
                {
                    'guesses': int,
                    'winners': int,
                    'find_best': bool,
                    'punish_more': bool
                },
                defaults={
                    'find_best': True,
                    'winners': 3,
                    'guesses': 1,
                    'punish_more': True,
                },
                ignore_arg_zero=False
            )
        except arg_parser.ParserError as e:
            return f'@{msg.user}, Unexpected error when processing arguments: {e.message}'
        if msg.channel in self.mailbox_games:
            return (f'@{msg.user}, Game is already running in this channel. '
                    f'If you want to override the game use "{argv[0]} cancel", then "{msg.text}"')

        if action_args['guesses'] < 1:
            return f'@{msg.user}, Number of guesses cannot be less than one.'

        action_args['start_time'] = time.time()
        self.mailbox_games[msg.channel] = action_args
        return (f'Mail minigame starts now! You get {action_args["guesses"]} '
                f'guess{"es" if action_args["guesses"] != 1 else ""}. Format is 30 32 29.')

    def _mailbox_draw(self, argv, msg):
        if msg.channel not in self.mailbox_games:
            return f'@{msg.user}, Cannot draw a winner from mailbox minigame, there is none running. FeelsBadMan'
        settings = self.mailbox_games[msg.channel]
        if settings.get('timeout_reason'):
            return (f'@{msg.user}, There is no minigame running, however there are automatic timeouts set up. '
                    f'Use "{argv[0]} cancel" to stop timing out.')
        action_argv = ' '.join(argv[2:])

        show_closed = False
        if 'end_time' not in settings:
            settings['end_time'] = time.time()
            show_closed = True

        match = GUESS_PATTERN.match(action_argv)
        if not match:
            return (
                f'@{msg.user}, Bad winning value, it should be formatted like "30 32 29" '
                f'{"The game has been automatically closed and is waiting for valid scores." if show_closed else ""}'
            )

        good_value = [int(i.rstrip(', -')) for i in match.groups()]

        msgs = plugin_chat_cache.find_messages(msg.channel, min_timestamp=settings['start_time'],
                                               max_timestamp=settings['end_time'])

        possible_guesses = list(filter(lambda m: bool(GUESS_PATTERN.match(m.text)), msgs))

        print('possible', possible_guesses)
        good_guesses = self._find_good_guesses(possible_guesses, good_value, settings)
        print('good', good_guesses)
        best = self._best_guess(settings, good_guesses)
        print('best', best)
        print(settings)
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

        del self.mailbox_games[msg.channel]
        db_notif = (
            f'{"Failed to save to database. " if failed_save else ""}ID: {game_obj.id if not failed_save else "n/a"}'
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
            if game.get('timeout_reason'):
                return f'@{msg.user}, Stopped automatic timeouts.'

            if 'end_time' not in game:
                game['end_time'] = time.time()
                return 'Entries are now closed!'
            else:
                return (f'@{msg.user}, This game has closed '
                        f'({datetime.timedelta(seconds=round(time.time() - game["end_time"]))} ago). ')

    def _mailbox_cancel(self, msg):
        game = self.mailbox_games.get(msg.channel)
        if game:
            del self.mailbox_games[msg.channel]
            if game.get('timeout_reason') is not None:
                return f'@{msg.user}, Stopped timeouts.'
            return f'@{msg.user}, Canceled the ongoing game.'
        else:
            return f'@{msg.user}, There is no game to cancel.'

    def _mailbox_timeout(self, argv, msg):
        action_argv = ' '.join(argv[2:])
        if msg.channel in self.mailbox_games:
            return (f'@{msg.user}, Game is already running in this channel. '
                    f'If you want to override the game use "{argv[0]} cancel", then "{msg.text}"')
        reason = (action_argv
                  or plugin_manager.channel_settings[msg.channel].get(self.default_no_game_timeout_reason))
        self.mailbox_games[msg.channel] = {
            'timeout_reason': reason,
            'end_time': time.time()
        }
        return (
            f'@{msg.user}, Will now time out mailbox game guesses. '
            f'Use "{argv[0]} cancel" to stop timing out guesses.'
        )

    def _mailbox_whatif(self, argv, msg):
        # "!mailbox" "whatif" "ID SCORE SCORE SCORE"
        #                 [2:]
        args = argv[-1].split(' ', 1)
        if len(args) != 2:
            return f'@{msg.user}, Usage: {argv[0]} {argv[1]} ID SCORE SCORE SCORE'
        id_ = args[0]
        matches = args[1]
        if not id_.isnumeric():
            return f'@{msg.user}, Game ID must be a number.'

        with main.session_scope() as session:
            try:
                game = session.query(self.MailboxGame).filter(self.MailboxGame.id == int(id_)).one()
            except sqlalchemy.exc.NoResultFound:
                return f'@{msg.user}, Unable to fetch game ID {int(id_)!r}'

        match = GUESS_PATTERN.match(matches)
        if not match:
            return (f'@{msg.user}, Could not extract scores from your message. '
                    f'Usage: {argv[0]} {argv[1]} ID SCORE SCORE SCORE')

        good_value = [int(i.rstrip(', -')) for i in match.groups()]

        settings = game.settings
        msgs = []
        for i in game.guesses:
            platform, channel, user, guess = i.split(' ', 3)
            msg = main.StandardizedMessage(guess, user.strip('<>'), channel, main.Platform[platform.strip('[]')])
            msgs.append(msg)
        possible_guesses = msgs
        print('possible', possible_guesses)
        good_guesses = self._find_good_guesses(possible_guesses, good_value, settings)
        print('good', good_guesses)
        best = self._best_guess(settings, good_guesses)
        print('best', best)
        print(settings)

        if len(best) == 0:
            return f'No matching guesses.'

        else:
            message = f'Best guesses would be {self._nice_best_guesses(best)}.'
            if len(message) > 500:
                msgs = []
                for i in range(1, math.ceil(len(message) / 500) + 1):
                    msgs.append(message[(i - 1) * 500:i * 500])
                return msgs
            return message

    # endregion

    # region mailbox draw helpers
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
            point_values = [g == good[num] for num, g in enumerate(guess)]
            points = sum(point_values)

            if i.user in good_guesses:  # check if user had a better guess before
                if guess != good_guesses[i.user]['parsed']:
                    # Don't count up duplicate guesses if they are the same,
                    # they were probably sent by mistake.
                    good_guesses[i.user]['count'] += 1

                if good_guesses[i.user]['count'] > settings['guesses']:
                    if settings['punish_more']:
                        good_guesses[i.user]['quality'] = 0
                    continue  # ignore any further guesses.
                if good_guesses[i.user]['quality'] < points:
                    good_guesses[i.user]['quality'] = points
                    good_guesses[i.user]['msg'] = i
                    good_guesses[i.user]['parsed'] = guess
                    good_guesses[i.user]['guessed'] = point_values
            else:
                good_guesses[i.user] = {
                    'quality': points,
                    'msg': i,
                    'parsed': guess,
                    'count': 1,
                    'guessed': point_values
                }

        return good_guesses

    def _nice_best_guesses(self, best):
        output = []
        for i in best:
            good_indicators = "".join("+" if v else "-" for v in i["guessed"])
            is_sub = any([i.startswith('subscriber') for i in i['msg'].flags.get('badges', [])])
            output.append(f'@{i["msg"].user} {"(Sub)" if is_sub else ""} ({i["quality"]}/3 {good_indicators})')
        return ', '.join(output)
    # endregion
    # endregion
