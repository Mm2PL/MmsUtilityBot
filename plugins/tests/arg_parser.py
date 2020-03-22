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
import re
import unittest
from unittest import TestCase

try:
    from ..utils import arg_parser
except ImportError:
    from .utils import arg_parser


class Test(TestCase):
    # general tests
    def test_parse_args_unknown(self):
        try:
            arg_parser.parse_args('this is a simple test', args_types={})
        except arg_parser.ParserError:
            return
        self.fail()

    def test_parse_args_bool_not_specified(self):
        try:
            arg_parser.parse_args('+test', args_types={})
        except arg_parser.ParserError:
            return
        self.fail()

    def test_parse_args_bool_specified(self):
        output = arg_parser.parse_args('+test', args_types={'test': bool})
        self.assertEqual(output, {'test': True})

    def test_parse_args_positional(self):
        output = arg_parser.parse_args('argument', args_types={0: str})
        self.assertEqual(output, {0: 'argument'})

    # converters
    def test_parse_args_str(self):
        output = arg_parser.parse_args('test=value', args_types={'test': str})
        self.assertEqual(output, {'test': 'value'})

    def test_parse_args_int(self):
        output = arg_parser.parse_args('test=1', args_types={'test': int})
        self.assertEqual(output, {'test': 1})

    def test_parse_args_float(self):
        output = arg_parser.parse_args('test=1.5', args_types={'test': float})
        self.assertEqual(output, {'test': 1.5})

    def test_parse_args_int_try_float(self):
        try:
            arg_parser.parse_args('test=1.5', args_types={'test': int})
        except arg_parser.ParserError:
            return
        self.fail()

    def test_parse_args_int_try_str(self):
        try:
            arg_parser.parse_args('test=invalid_string', args_types={'test': int})
        except arg_parser.ParserError:
            return
        self.fail()

    def test_parse_args_float_try_str(self):
        try:
            arg_parser.parse_args('test=invalid_string', args_types={'test': float})
        except arg_parser.ParserError:
            return
        self.fail()

    def test_parse_duplicate_argument(self):
        try:
            arg_parser.parse_args('test:test test:test', {'test': str})
        except arg_parser.ParserError:
            pass
        else:
            self.fail()
        try:
            arg_parser.parse_args('+test +test', {'test': bool})
        except arg_parser.ParserError:
            pass
        else:
            self.fail()

        try:
            arg_parser.parse_args('-test -test', {'test': bool})
        except arg_parser.ParserError:
            pass
        else:
            self.fail()

        try:
            arg_parser.parse_args('-test +test', {'test': bool})
        except arg_parser.ParserError:
            pass
        else:
            self.fail()

    def test_converter_timedelta_single(self):
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1s'),
                         datetime.timedelta(seconds=1))
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1m'),
                         datetime.timedelta(seconds=60))
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1h'),
                         datetime.timedelta(seconds=60 * 60))
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1d'),
                         datetime.timedelta(seconds=60 * 60 * 24))
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1w'),
                         datetime.timedelta(seconds=60 * 60 * 24 * 7))
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1y'),
                         datetime.timedelta(seconds=60 * 60 * 24 * 365))

    def test_converter_timedelta_multiple(self):
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1m1s'),
                         datetime.timedelta(seconds=61))

    def test_converter_timedelta_all(self):
        self.assertEqual(arg_parser._time_converter(datetime.timedelta, {}, '1y1w1d1h1m1s'),
                         datetime.timedelta(seconds=(60 * 60 * 24 * 365
                                                     + 60 * 60 * 24 * 7
                                                     + 60 * 60 * 24
                                                     + 60 * 60
                                                     + 60
                                                     + 1)))

    def test_converter_datetime(self):
        now = datetime.datetime.now()
        self.assertEqual(arg_parser._time_converter(datetime.datetime, {},
                                                    now.strftime('%Y-%m-%d %H:%M:%S.%f')),
                         now)

        now = datetime.datetime.fromtimestamp(round(now.timestamp()))
        self.assertEqual(arg_parser._time_converter(datetime.datetime, {'format': '%Y-%m-%d %H:%M:%S'},
                                                    now.strftime('%Y-%m-%d %H:%M:%S')),
                         now)

    def test_converter_regex(self):
        test_string = 'this is a test'
        result = arg_parser._regex_converter('regex', {
            'regex': re.compile(r'this ?is ?a ?test')
        }, test_string)
        if not result or result[0] != test_string:
            self.fail('regex didn\'t match')

    def test_converter_regex_bad_input(self):
        test_string = 'this isn\'t a test'
        result = arg_parser._regex_converter('regex', {
            'regex': re.compile(r'this ?is ?a ?test')
        }, test_string)
        if result:
            self.fail()

    def test_converter_regex_string_pattern(self):
        test_string = 'this is a test'
        result = arg_parser._regex_converter('regex', {
            'regex': r'this ?is ?a ?test'
        }, test_string)
        if not result or result[0] != test_string:
            self.fail('regex didn\'t match')

    def test_converter_regex_invalid_pattern(self):
        try:
            arg_parser._regex_converter('regex', {
                'regex': 0
            }, 'test')
        except arg_parser.ParserError:
            return
        self.fail()

    def test_converter_regex_missing_pattern(self):
        try:
            arg_parser._regex_converter('regex', {}, 'test')
        except arg_parser.ParserError:
            return
        self.fail()

    # split test
    def test_split_args(self):
        self.assertEqual(arg_parser._split_args('this is a simple test'), ['this', 'is', 'a', 'simple', 'test'])

    def test_split_args_quote(self):
        self.assertEqual(arg_parser._split_args('this is a "simple test"'), ['this', 'is', 'a', 'simple test'])

    def test_split_args_escape_space(self):
        self.assertEqual(arg_parser._split_args('this is a simple\\ test'), ['this', 'is', 'a', 'simple test'])

    def test_split_args_bad_quote(self):
        try:
            arg_parser._split_args('this is a simple test"', strict_quotes=True)
        except arg_parser.ParserError:
            return
        self.fail()

    def test_split_args_bad_escape(self):
        try:
            arg_parser._split_args('this is a simple test\\', strict_escapes=True)
        except arg_parser.ParserError:
            return
        self.fail()

    def test_split_args_bad_escape_middle(self):
        try:
            arg_parser._split_args('this is \\a simple test', strict_escapes=True)
        except arg_parser.ParserError:
            return
        self.fail()

    def test_split_args_escape_backslash(self):
        self.assertEqual(arg_parser._split_args('\\\\', strict_escapes=True), ['\\'])

    def test_split_args_escape_backslash_sideeffects(self):
        self.assertEqual(arg_parser._split_args('\\\\ ', strict_escapes=True), ['\\'])

    def test_split_args_escape_quote(self):
        self.assertEqual(arg_parser._split_args('\\"', strict_escapes=True), ['"'])

    def test_split_args_unknown_escape_non_scrict(self):
        self.assertEqual(arg_parser._split_args('\\a', strict_escapes=False), ['\\a'])

    def test_split_args_tailing_backslash_non_strict(self):
        self.assertEqual(arg_parser._split_args('\\', strict_escapes=False), ['\\'])

    # handle_typed_argument
    def test_handle_typed_argument_tuple_converter(self):
        arg_parser.handle_typed_argument('1', (int, {}))

    def test_handle_typed_argument_unknown_converter(self):
        def _test(test):
            return test

        self.assertEqual(arg_parser.handle_typed_argument('1', (_test, {})), '1')

    def test_handle_typed_argument_known_converter(self):
        self.assertEqual(arg_parser.handle_typed_argument('1h', (datetime.timedelta, {})), datetime.timedelta(hours=1))

    def test_handle_typed_argument_uncallable_unknown_converter(self):
        try:
            arg_parser.handle_typed_argument('asd', ('non_existent_converter', {}))
        except arg_parser.ParserError:
            return
        self.fail()

    # check_missing_keys
    def test_check_missing_keys_empty(self):
        self.assertEqual(arg_parser.check_required_keys({}, []), [])

    def test_check_missing_keys_missing_required_key(self):
        self.assertEqual(arg_parser.check_required_keys({}, ['test']), ['test'])

    # _fill_optional_keys
    def test_fill_optional_keys_empty(self):
        before = {}
        new = before.copy()
        arg_parser._fill_optional_keys(new, {})
        self.assertEqual(new, before)

    def test_fill_optional_keys_missing_required_key(self):
        test = {}
        arg_parser._fill_optional_keys(test, {'test': str})
        self.assertEqual(test, {'test': ...})

    def test_fill_optional_keys_additional(self):
        test = {'test': 'test'}
        arg_parser._fill_optional_keys(test, {'test': str})
        self.assertEqual(test, {'test': 'test'})

    # _parse_simple_value
    def test_parse_simple_value_normal(self):
        self.assertEqual(arg_parser._parse_simple_value('a=b', ['a=b'], 0), ('a', 'b'))

    def test_parse_simple_value_with_space(self):
        self.assertEqual(arg_parser._parse_simple_value('a=', ['a=', 'b'], 0), ('a', 'b'))


if __name__ == '__main__':
    unittest.main(verbosity=2, warnings='error')
