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
import typing

import regex


class ParserError(Exception):
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return f'<ParserError: {self.message}>'

    def __str__(self):
        return f'ParserError: {self.message}'


def parse_args(text: str, args_types: dict):
    args = {

    }
    argv = text.split(' ')
    for num, token in enumerate(argv):
        if ':' in token or '=' in token:
            _parse_simple_value(token, argv, num)
        elif token.startswith('+'):
            args[token.lstrip('+')] = True
        elif token.startswith('-'):
            args[token.lstrip('-')] = False

    _parse_non_string_args(args, args_types)  # args is modified

    return args


def _parse_simple_value(token: str, argv: typing.List[str], num: int):
    token2 = token.replace(':', '=', 1).split('=', 1)
    if len(token2) == 1:  # expect a value after a space.
        if len(argv) >= num + 1:
            token2.append(argv[num + 1])
        else:
            raise ParserError(f'Expected value after token {token2[0]}')
    # else: key and value is in token2.
    return token2[0], token2[1]


def _parse_non_string_args(args, args_types):
    for key, value in args.copy():
        if key in args_types:
            type_ = args_types[key]
            args[key] = _handle_typed_argument(value, type_)
        else:
            raise ParserError(f'Unexpected argument: {key}')


TIMEDELTA_REGEX = regex.compile(r'(?:(?P<days>\d+)d(?:ays)?)?'
                                r'(?:(?P<hours>[0-5]?\d)h(?:ours?)?)?'
                                r'(?:(?P<minutes>[0-5]?\d)m(?:inutes?)?)?'
                                r'(?:(?P<seconds>[0-5]?\d)s(?:econds?)?)?')


def _time_converter(converter, options, value):
    if converter == datetime.datetime:
        if 'format' in options:
            f = options['format']
        else:
            f = '%Y-%m-%d %H:%M:%S.%f'
        try:
            return datetime.datetime.strptime(value, f)
        except Exception as e:
            raise ParserError(f'Cannot parse {value!r} as {converter} with date string {options["format"]!r}') \
                from e
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


known_converters: typing.Dict[typing.Type, typing.Callable] = {
    datetime.timedelta: _time_converter,
    datetime.datetime: _time_converter,
}


def _handle_typed_argument(value: str, type_) -> typing.Any:
    converter: type = type_
    options: dict = {}
    if isinstance(type_, tuple):
        converter, options = type_
    if converter == int:
        if value.isnumeric():
            return int(type_)
        else:
            return ParserError(f'Cannot parse {value!r} as {type_}')
    elif converter == str:
        return value
    elif converter in known_converters:
        return known_converters[converter](converter, options, value)
    elif isinstance(converter, typing.Callable):  # try calling the converter directly as a last ditch effort.
        return converter(value, **options)
    else:
        raise ParserError(f'Cannot parse {value!r} as {converter!r}. Unknown converter: {converter!r}')
