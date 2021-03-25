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
import datetime
import typing

import regex


class ParserError(ValueError):
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return f'<ParserError: {self.message}>'

    def __str__(self):
        return f'ParserError: {self.message}'


POSITIONAL = -1


def parse_args(text: str, args_types: dict, strict_escapes=True, strict_quotes=False, no_arg_fill=False,
               ignore_arg_zero=True, defaults: typing.Optional[typing.Dict[str, typing.Any]] = None):
    """
    Parse arguments from text.
    Accepted formats:
      - Key=value
      - Key:value
      - Key= value
      - Key: value

    :param text: Text to parse
    :param args_types: Types for arguments. Used when converting strings into appropriate datatypes
    :param strict_escapes: Should \\\\ escapes be strict. Unknown escapes and trailing backslashes will raise \
    exceptions if this is true
    :param strict_quotes: Should quotes (") be strict. Unclosed quotes will raise exceptions if this is true
    :param no_arg_fill: Fills arguments that are not present with Ellipsis, if defaults are present, they will \
    overwrite the Ellipsis
    :param ignore_arg_zero: If true, positional argument #0 in the input will be ignored when it's unexpected.
    :param defaults: Default values for arguments, will not be modified. NOTE: mutable objects will not be deep copied.
    :return: Parsed out arguments as a Dict[str, Any]
    """
    text = text.rstrip(' \U000E0000')
    args = {}
    current_positional = 0
    argv = _split_args(text, strict_escapes=strict_escapes, strict_quotes=strict_quotes)
    to_skip = None
    for num, token in enumerate(argv.copy()):
        if to_skip is not None and to_skip > num:
            continue
        if ':' in token or '=' in token:
            k, v, count_consumed = _parse_simple_value(token, argv, num)
            if count_consumed > 1:
                to_skip = num + count_consumed
            if k in args:
                raise ParserError(f'Duplicate argument: {k}')
            args[k] = v
        elif token.startswith(('-', '+')):
            if token.startswith('-'):
                arg_key = token.lstrip("-")
                val = False
                if token.startswith('--'):
                    val = True
            else:
                arg_key = token.lstrip('+')
                val = True

            if arg_key in args:
                raise ParserError(f'Duplicate argument: {arg_key}')
            if arg_key not in args_types:
                raise ParserError(f'Unknown argument: {arg_key}')

            if args_types[arg_key] is not bool:
                raise ParserError(f'Cannot use argument {arg_key} as [+-]{arg_key}, type of {arg_key} is not boolean.')

            args[arg_key] = val
        else:
            if current_positional in args_types or POSITIONAL in args_types:
                args[current_positional] = token
            else:
                if num != 0 or not ignore_arg_zero:
                    raise ParserError(f'Unexpected positional argument {current_positional}: {token!r}')
            current_positional += 1

    _parse_non_string_args(args, args_types)  # args is modified
    if defaults is not None:
        for k, v in defaults.items():
            if k not in args_types:
                raise ValueError(f'Argument {k} has a default, but no type in arg_types.')
            if k not in args:
                args[k] = v
    else:
        if not no_arg_fill:
            _fill_optional_keys(args, args_types)  # args is modified
    return args


def split_args(text, strict_escapes=True, strict_quotes=False,
               escapes: typing.Optional[typing.Dict[str, str]] = None) -> typing.List[str]:
    return _split_args(text, strict_escapes, strict_quotes, escapes)


def _split_args(text, strict_escapes=True, strict_quotes=False,
                escapes: typing.Optional[typing.Dict[str, str]] = None) -> typing.List[str]:
    if escapes is None:
        escapes = {
            '\\\\': '\\',
            '\\|': '|',
            '\\"': '"'
            # r'\ ' is a special case
        }
    is_quoted = False
    is_escaped = False
    quote_start = -1
    argv = ['']
    for num, letter in enumerate(text):
        if letter == '\\':
            if is_escaped:
                argv[-1] += letter
                is_escaped = False
            else:
                is_escaped = True
            continue
        elif not is_escaped and letter == '"':
            is_quoted = not is_quoted
            if is_quoted:
                quote_start = num
            else:
                quote_start = -1
        elif letter == ' ':
            if is_escaped or is_quoted:
                argv[-1] += letter
            else:
                argv.append('')  # begin new argument
        else:
            if is_escaped:
                if '\\' + letter in escapes:
                    argv[-1] += escapes['\\' + letter]
                elif strict_escapes:
                    raise ParserError(f'Unknown escape: \\{letter} at position #{num}, did you want \\\\? '
                                      f'[strict_escapes]')
                else:
                    argv[-1] += '\\'
                    argv[-1] += letter
            else:
                argv[-1] += letter
        is_escaped = False
    if is_quoted and strict_quotes:
        raise ParserError(f'Unclosed quotation, starting from character #{quote_start} [strict_quotes]')
    if is_escaped:
        if strict_escapes:
            raise ParserError('Trailing backslash. [strict_escapes]')
        else:
            argv[-1] += '\\'
    while '' in argv:
        argv.remove('')
    return argv


def _parse_simple_value(token: str, argv: typing.List[str], num: int) -> typing.Tuple[str, str, int]:
    token2 = token.replace(':', '=', 1).split('=', 1)
    count_consumed = 1
    if len(token2[1]) == 0:  # expect a value after a space.
        count_consumed = 2
        if len(argv) > num + 1:
            token2[1] = argv[num + 1]
            if token2[1].endswith(('=', ':')):  # make `a0: a1: value` be interpreted as {"a0": "", "a1": "value"}
                token2[1] = ''
                count_consumed -= 1
        else:
            raise ParserError(f'Expected a value after {token2[0]!r}.')
    # else: key and value is in token2.
    return token2[0], token2[1], count_consumed


def _parse_non_string_args(args, args_types):
    for key, value in args.copy().items():
        if key in args_types:
            args[key] = handle_typed_argument(value, args_types[key])
        else:
            if isinstance(key, int) and POSITIONAL in args_types:
                args[key] = handle_typed_argument(value, args_types[POSITIONAL])
            else:
                raise ParserError(f'Unexpected argument: {key}')


TIMEDELTA_REGEX = regex.compile(r'^(?:(?P<years>\d+)y(?:ears?)?)?'
                                r'(?:(?P<weeks>\d+)w(?:weeks?)?)?'
                                r'(?:(?P<days>\d+)d(?:ays?)?)?'
                                r'(?:(?P<hours>[0-5]?\d)h(?:ours?)?)?'
                                r'(?:(?P<minutes>[0-5]?\d)m(?:inutes?)?)?'
                                r'(?:(?P<seconds>[0-5]?\d)s(?:econds?)?)?$')


def _time_converter(converter, options, value):
    if converter == datetime.datetime:
        return _datetime_from_string(options, value)
    elif converter == datetime.timedelta:
        if 'regex' in options:
            match = regex.match(options['regex'], value)
            if match is None:
                raise ParserError(f'Cannot parse {value!r} as {converter} with regex {options["regex"]}')
        else:
            match = TIMEDELTA_REGEX.match(value)
            if match is None:
                raise ParserError(f'Cannot parse {value!r} as {converter} with default regex.')
        m = match.groupdict()
        seconds = float(m.get('seconds') if m.get('seconds', None) is not None else 0)
        seconds += 60 * float(m.get('minutes') if m.get('minutes', None) is not None else 0)
        seconds += 60 * 60 * float(m.get('hours') if m.get('hours', None) is not None else 0)
        seconds += 60 * 60 * 24 * float(m.get('days') if m.get('days', None) is not None else 0)
        seconds += 60 * 60 * 24 * 7 * float(m.get('weeks') if m.get('weeks', None) is not None else 0)
        seconds += 60 * 60 * 24 * 365 * float(m.get('years') if m.get('years', None) is not None else 0)
        return datetime.timedelta(seconds=seconds)


def _datetime_from_string(options, data: str) -> datetime.datetime:
    includes_end = options.get('includes_end')
    if includes_end is None:
        raise ValueError('Missing `includes_end` option')

    if 'format' in options:
        formats = (options['format'],)
    elif 'formats' in options:
        formats = options['formats']
    else:
        formats = (
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S.%fZ',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%m-%d',
            '%m/%d',

            '%d.%m.%Y',
            '%d.%m.%Y %H:%M:%S',
            '%x'
        )
    now = datetime.datetime.utcnow()
    for f in formats:
        try:
            o = datetime.datetime.strptime(data, f)
            if o.year == 1900 and '%Y' not in f:
                o = o.replace(year=now.year)
            if o.month == 1 and '%m' not in f:
                o = o.replace(month=now.month)
            if o.day == 1 and '%d' not in f:
                if includes_end:
                    if o.month == 2:
                        if (o.year % 4 == 0 and o.year % 100 != 0) or o.year % 400 == 0:
                            o = o.replace(day=29)
                        else:
                            o = o.replace(day=28)
                    else:
                        if o.month in (1, 3, 5, 7, 8, 10, 12):
                            o = o.replace(day=31)
                        else:
                            o = o.replace(day=30)
                else:
                    o = o.replace(day=1)

            if o.hour == 0 and '%H' not in f:
                o = o.replace(hour=23 if includes_end else 0)
            if o.minute == 0 and '%M' not in f:
                o = o.replace(minute=59 if includes_end else 0)
            if o.second == 0 and '%S' not in f:
                o = o.replace(second=59 if includes_end else 0)

            return o
        except ValueError:
            continue

    raise ParserError(f'Cannot parse {data!r} as a datetime.')


def _regex_converter(converter, options, value):
    if 'regex' in options:
        if isinstance(options['regex'], (str, bytes)):
            pat = regex.compile(options['regex'])
            nice_pattern = options['regex']
        elif hasattr(options['regex'], 'pattern'):
            pat = regex.compile(options['regex'].pattern)
            nice_pattern = options['regex'].pattern
        else:
            raise ParserError(f'Cannot parse {value!r} as {converter}, regular expression provided was '
                              f'{type(options["regex"])}, expected a compiled pattern, string or bytes-like object.')

        val = pat.match(value)
        if val is None:
            raise ParserError(f"Argument {value!r} does not match expected pattern: "
                              f"{repr(nice_pattern)[:50]}{'…' if len(nice_pattern) > 50 else ''}.")
        return val
    else:
        raise ParserError(f'Cannot parse {value!r} as {converter} without a regular expression.')


known_converters: typing.Dict[typing.Union[typing.Type, str], typing.Callable] = {
    datetime.timedelta: _time_converter,
    datetime.datetime: _time_converter,
    'regex': _regex_converter,
}


def handle_typed_argument(value: str, type_) -> typing.Any:
    converter: type = type_
    options: dict = {}
    if isinstance(type_, tuple):
        converter, options = type_
    if converter == int:
        if value.isdecimal():
            return int(value)
        else:
            raise ParserError(f'Cannot parse {value!r} as {type_}')
    elif converter == float:
        try:
            return float(value)
        except ValueError as e:
            raise ParserError(f'Cannot parse {value!r} as {type_}') from e
    elif converter == str:
        return value
    elif converter in known_converters:
        return known_converters[converter](converter, options, value)
    elif isinstance(converter, typing.Callable):  # try calling the converter directly as a last ditch effort.
        return converter(value, **options)
    else:
        raise ParserError(f'Cannot parse {value!r} as {converter!r}. Unknown converter: {converter!r}')


def check_required_keys(args, required):
    missing = []
    for k in required:
        if k not in args or args[k] is Ellipsis:
            missing.append(k)
    return missing


def _fill_optional_keys(args, arg_types):
    for a in arg_types:
        if a not in args and a != POSITIONAL:
            args[a] = Ellipsis
