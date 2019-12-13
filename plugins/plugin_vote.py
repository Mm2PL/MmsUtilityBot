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
import shlex
import typing
import re

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()
try:
    import plugin.plugin_su as plugin_su
except ImportError:
    plugin_su = None  # plugin not enabled, don't have to worry about real usernames

# noinspection PyUnresolvedReferences
import twitchirc

__meta_data__ = {
    'name': 'plugin_votes',
    'commands': [
        'vote',
        'poll'
    ]
}
log = main.make_log_function('votes')

votes = {
    # 'channel': {
    #     '__vote_info': Vote()
    # }

}


class Vote:
    def __init__(self, name, channel, options=None, allow_multiple=False):
        self.channel = channel
        if options is None:
            options = ['Yes', 'No']
        self.name = name
        self.options = options
        self.closed = False
        self.allow_multiple = allow_multiple

    @property
    def results(self):
        counted_up = {opt: 0 for opt in self.options}
        if self.allow_multiple:
            results: typing.Dict[str, typing.Union[typing.List[str, str], Vote]] = votes[self.channel].copy()
            del results['__vote_info']
            for user, voted_for in results.items():
                for i in voted_for:
                    counted_up[i] += 1
        else:
            results: typing.Dict[str, typing.Union[str, Vote]] = votes[self.channel].copy()
            del results['__vote_info']

            for voted_for in results.copy().values():
                counted_up[voted_for] += 1
        return counted_up

    def close(self):
        global votes
        if self.closed:
            log('WARN', f'Running `close()` on a closed Vote ({self.name},{self.options}@{self.channel} '
                        f'name,options@channel)')
            return

        counted_up = self.results
        self.closed = True
        votes[self.channel] = {
            '__vote_info': self,
            '__vote_results': counted_up.copy()
        }
        return counted_up


def get_user_name(msg):
    if plugin_su is not None:
        return msg.real_user
    else:
        return msg.user


@main.bot.add_command('vote')
def command_vote(msg: twitchirc.ChannelMessage):
    if msg.user in ['__vote_info', '__vote_results']:
        return f'@{get_user_name(msg)} No crashing the bot for you ;)'
        return
    cd_state = main.do_cooldown('vote', msg, global_cooldown=0, local_cooldown=1 * 60)
    if cd_state:
        return

    if msg.channel not in votes:
        return f"@{get_user_name(msg)} There's no on-going vote in this channel."
    else:
        vote_obj: Vote = votes[msg.channel]['__vote_info']
        if vote_obj.closed:
            return f"@{get_user_name(msg)} There's no on-going vote in this channel."
        argv = msg.text.split(' ')
        if len(argv) < 2:
            return f'@{get_user_name(msg)} Usage: !vote <option(s)>'
        already_voted = msg.user in votes[msg.channel]
        if votes[msg.channel]['__vote_info'].allow_multiple:
            user_votes = argv[1].split(',') if ',' in argv[1] else [argv[1]]
            invalid_votes = []
            for i in user_votes:
                if i not in vote_obj.options:
                    invalid_votes.append(i)

            if not invalid_votes:
                votes[msg.channel][msg.user] = user_votes
                if already_voted:
                    main.bot.send(msg.reply(f'@{get_user_name(msg)} Successfully overridden vote. '
                                            f'New vote is {user_votes!r}'))
                else:
                    return f'@{get_user_name(msg)} Successfully voted for {user_votes!r}'
            else:

                if len(invalid_votes) == 1:
                    return f'@{get_user_name(msg)} Invalid option: {invalid_votes[0]!r}'
                else:
                    return f'@{get_user_name(msg)} Invalid option(s): {invalid_votes!r}'
        if argv[1] in vote_obj.options:
            votes[msg.channel][msg.user] = argv[1]
            if already_voted:
                main.bot.send(msg.reply(f'@{get_user_name(msg)} Successfully overridden vote. '
                                        f'New vote is {argv[1]!r}'))
            else:
                return f'@{get_user_name(msg)} Successfully voted for {argv[1]!r}'
        else:
            if ',' in argv[1]:
                return f'@{get_user_name(msg)} Cannot vote for multiple options in this poll.'
            else:
                return f'@{get_user_name(msg)} Invalid option: {argv[1]}'


def _nice_winners(winners):
    print(winners)
    if len(winners) == 1:
        return f'{winners[0][1].capitalize()} won with {winners[0][0]} votes.'
    else:
        return (f"It\'s a tie between "
                f"{', '.join([f'{i[1]}' for i in winners])[::-1].replace(' ,', ' and '[::-1], 1)[::-1]}")


def _calculate_votes(results):
    output = []
    all_votes = sum(results.values())
    if all_votes == 0:
        return '[no votes]'
    winners = [(0, '')]
    for key, value in results.items():
        output.append(f'{value} ({value / all_votes * 100:.2f}%) votes for {key!r}')
        if value > winners[0][0]:
            winners = [(value, key)]
        elif value == winners[0][0]:
            winners.append((value, key))
    return ", ".join(output) + f'. {_nice_winners(winners)}'


vote_admin_parser = twitchirc.ArgumentParser(prog='!poll', add_help=False)
vap_gr1 = vote_admin_parser.add_mutually_exclusive_group()
# name,COMMA-SEPARATED-VOTES
vap_gr1.add_argument('-n', '--new', help='Create a poll.', dest='new',
                     metavar=('NAME', 'COMMA_SEPARATED_OPTIONS'), nargs=2)
vap_gr1.add_argument('-e', '--end', help='Stop the poll and calculate the results.', dest='end',
                     action='store_true')
vote_admin_parser.add_argument('-m', '--allow-multiple', help='Allow voting for multiple options', dest='multiple',
                               action='store_true', default=False)
vap_gr1.add_argument('-t', '--template', help='Create a poll from a template', dest='new_from_template',
                     metavar='TEMPLATE_NAME')
vap_gr1.add_argument('--new-template', help='Create a new template', dest='new_template', nargs=2,
                     metavar=('(NAME)', '(COMMA SEPARATED OPTIONS)'))


def _ensure_plugin_data():
    if 'plugin_vote' in main.bot.storage.data:
        if 'templates' not in main.bot.storage.data['plugin_vote']:
            main.bot.storage['plugin_vote']['templates'] = []
    else:
        main.bot.storage['plugin_vote'] = {
            'templates': {

            }
        }


def _load_template(template_name):
    _ensure_plugin_data()
    templates = main.bot.storage['plugin_vote']['templates']
    if template_name in templates:
        return templates[template_name]


@main.bot.add_command('poll', required_permissions=['poll.manage'], enable_local_bypass=True)
def command_vote_admin(msg: twitchirc.ChannelMessage):
    args = vote_admin_parser.parse_args(shlex.split(msg.text.replace('!poll', '', 1)))

    print(msg.channel, msg.user, args)
    if args is None:
        usage = re.sub('\n +', ' ', vote_admin_parser.format_usage())
        return f"@{get_user_name(msg)} {usage}"
    if not args.new_template and not args.new_from_template and not args.end and not args.new:
        usage = re.sub('\n +', ' ', vote_admin_parser.format_usage())
        return f"@{get_user_name(msg)} {usage}"

    elif args.new_template:
        _ensure_plugin_data()
        main.bot.storage['plugin_vote']['templates'][args.new_template[0]] = args.new_template
        main.bot.storage.save()
    elif args.new_from_template:
        template = _load_template(args.new_from_template)
        if template is None:
            return f'@{get_user_name(msg)} Cannot retrieve template: {args.new_from_template!r}'
        args.new = template
    elif args.end:
        if msg.channel not in votes:
            return f"@{get_user_name(msg)} There's no on-going vote in this channel."
        vote_obj: Vote = votes[msg.channel]['__vote_info']
        results = vote_obj.close()

        return (f'@{get_user_name(msg)} The results are: '
                f'{_calculate_votes(results)}')

    if args.new:
        if msg.channel in votes and not votes[msg.channel]['__vote_info'].closed:
            return (f"@{get_user_name(msg)} There's already a un-closed poll in this channel. "
                    f"TIP: Use -e/--end to close it.")
        vote = Vote(args.new[0], msg.channel, options=args.new[1].split(','), allow_multiple=args.multiple)
        votes[msg.channel] = {
            '__vote_info': vote
        }
        return (f'@{get_user_name(msg)} Created new poll {args.new[0]!r} with options '
                f'{args.new[1].split(",")!r}.'
                f'{" Allowing voting for multiple options" if args.multiple else ""}')


command_vote_admin: twitchirc.Command
