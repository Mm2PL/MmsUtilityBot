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
# noinspection PyUnresolvedReferences
import twitchirc

__meta_data__ = {
    'name': 'plugin_reminders',
    'commands': []
}
log = main.make_log_function('reminders')
reminders: typing.Dict[str, typing.List[typing.Dict[str, typing.Union[str, int]]]] = {
    # 'channel': [
    #     {
    #         'text': 'some_text',
    #         'seconds': 0,
    #         'timestamp': 0,
    #         'user': 'user'
    #     }
    # ]
}
TIME_STR_PATTERN = r'(?:([0-9]+)h)?([0-9]+)m(?:([0-9]+)s)?'


def process_time(time_string: str) -> int:
    m = re.match(TIME_STR_PATTERN, time_string)
    if m:
        print(m, m[1], m[2], m[3], m[0])
        seconds = (
                ((int(m[1]) * 3600) if m[1] is not None else 0)
                + (int(m[2]) * 60)
                + ((int(m[3])) if m[3] is not None else 0)
        )
        return seconds
    return -1


c_rem_parser = twitchirc.ArgumentParser(prog='!reminder', add_help=False)
c_rem_action = c_rem_parser.add_mutually_exclusive_group(required=True)
# {
c_rem_action.add_argument('-a', '--add', dest='add', metavar='TEXT', nargs='+')
c_rem_action.add_argument('-h', '--help', dest='help', action='store_true')
c_rem_action.add_argument('-l', '--list', dest='list', action='store_true')
c_rem_action.add_argument('-r', '--remove', dest='remove', metavar='USER')
# }
c_rem_parser.add_argument('-t', '--time', dest='time', metavar='[0h]10m[0s]', default='0h10m0s')
c_rem_parser.add_argument('-nr', '--no-remove', dest='nr', action='store_true', default=False)
c_rem_parser.add_argument('-f', '--for', dest='for_user', default=None)


@main.add_alias(main.bot, 'r')
@main.bot.add_command(command='reminder', forced_prefix=None, enable_local_bypass=True,
                      required_permissions=['plugin_reminder.reminder'])
def command_reminder(msg: twitchirc.ChannelMessage):
    aargs = c_rem_parser.parse_args(msg.text.split(' ')[1:])
    if aargs is None or aargs.help:
        main.bot.send(msg.reply(f'@{msg.user} {c_rem_parser.format_usage()}'))
        return
    # for i in dir(aargs):
    #     if i.startswith('_'):
    #         continue
    #     print(i, getattr(aargs, i, None))
    if aargs.for_user:
        missing_perms = main.bot.check_permissions(msg, ['reminder.reminder.for_other'], enable_local_bypass=True)
        if missing_perms:
            main.bot.send(msg.reply(f'@{msg.user} Cannot add reminder for other user, you don\'t have the permissions '
                                    f'needed'))
    if aargs.remove:
        if msg.channel not in reminders:
            main.bot.send(msg.reply(f'@{msg.user} Cannot remove reminders: channel is not registered. '
                                    f'No reminders here.'))
            return
        count = 0
        for r in reminders[msg.channel].copy():
            if r['user'] == aargs.remove.lower():
                count += 1
                reminders[msg.channel].remove(r)
        main.bot.send(msg.reply(f'@{msg.user} removed {count} reminder(s).'))
    if aargs.list:
        output = ''
        if msg.channel not in reminders:
            main.bot.send(msg.reply(f'@{msg.user} Cannot list reminders: channel is not registered. '
                                    f'No reminders here.'))
            return
        for r in reminders[msg.channel]:
            output += f'<{r["text"]!r} on ' \
                      f'{datetime.datetime.fromtimestamp(r["timestamp"]).strftime("%Y-%M-%d %H:%m:%S")}>, '
        output = output[:-2]
        main.bot.send(msg.reply(f'@{msg.user} List: {output}'))
        return
    if aargs.add:
        # if not aargs.time:
        #     bot.send(msg.reply(f'@{msg.user} Argument -t/--time is required with -a/--add.'))
        #     return
        text = ' '.join(aargs.add)
        seconds = process_time(aargs.time)
        print(text, seconds)
        new_timestamp = time.time() + seconds
        if msg.channel not in reminders:
            reminders[msg.channel] = []
        reminders[msg.channel].append({
            'text': text,
            'seconds': seconds,
            'timestamp': new_timestamp,
            'user': msg.user,
            'nr': aargs.nr
        })
        if not aargs.nr:
            main.bot.send(msg.reply(f'@{msg.user} , I will be messaging you in {seconds} seconds '
                                    f'or ({seconds // 3600:.0f} hours, '
                                    f'{seconds % 3600 / 60:.0f} minutes and {seconds % 3600 % 60:.0f} seconds) with '
                                    f'the message {text!r}'))
        else:
            main.bot.send(msg.reply(f'@{msg.user} , I will be messaging you every {seconds} seconds '
                                    f'or ({seconds // 3600:.0f} hours, '
                                    f'{seconds % 3600 / 60:.0f} minutes and {seconds % 3600 % 60:.0f} seconds) with '
                                    f'the message {text!r}'))


def make_successful_set_reminder_message(msg, all_seconds, text, reoccurring):
    hours = all_seconds // 3600

    minutes = all_seconds % 3600 / 60
    seconds = all_seconds % 3600 % 60
    if hours == 1:
        hours_text = 'hour'
    elif hours == 0:
        hours_text = ''
    else:
        hours_text = f'{hours} hours'

    if minutes == 1:
        minutes_text = 'minute'
    elif minutes == 0:
        minutes_text = ''
    else:
        minutes_text = f'{minutes} minutes'

    if seconds == 1:
        seconds_text = 'second'
    elif seconds == 0:
        seconds_text = ''
    else:
        seconds_text = f'{seconds} seconds'

    time_pre_text = [hours_text, minutes_text, seconds_text]
    while '' in time_pre_text:
        time_pre_text.remove('')
    if not time_pre_text:
        main.black_list_user(msg.user, 5 * 60)
        return f'@{msg.user} WTF? WHY WOULD YOU WANT A REMINDER FOR 0 HOURS, 0 MINUTES, 0 SECONDS.' \
               f'[black-listed for 5 minutes]'
    time_text = ''

    separators = [',', 'and']
    for i, j in enumerate(time_pre_text):
        if i:  # current elem (hours, minutes or seconds) is not empty meaning that it wasn't zero.
            sep = ''

            time_text += i
    return (f'@{msg.user} , I will be messaging you {"every" if reoccurring else "in"} '
            f'{all_seconds} seconds or ({time_text}) with the message {text!r}')


def remind(reminder, channel):
    msg = twitchirc.ChannelMessage(user='OUTGOING', channel=channel,
                                   text=f'@{reminder["user"]} As promised I\'m reminding you: {reminder["text"]}')
    msg.outgoing = True
    main.bot.send(msg)
    if reminder['nr']:
        reminder['timestamp'] = time.time() + reminder['seconds']


def reminder_handler(event_name, msg: twitchirc.Message):
    del msg, event_name
    current_time = time.time()
    for channel in reminders:
        for r in reminders[channel].copy():
            if r['timestamp'] <= current_time:
                remind(r, channel)
                if not r['nr']:
                    reminders[channel].remove(r)


# main.bot.handlers['any_msg'].append(reminder_handler)
main.bot.schedule_repeated_event(0.11, 5, reminder_handler, (None, None), {})
