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
import unittest
from unittest import TestCase

try:
    from ..utils import arg_parser
except ImportError:
    from .utils import arg_parser


class Test(TestCase):
    # general tests
    def test_parse_args_unknown(self):
        # ignore unknown
        output = arg_parser.parse_args('this is a simple test', args_types={})
        self.assertEqual(output, {})

    def test_parse_args_bool_not_specified(self):
        try:
            arg_parser.parse_args('+test', args_types={})
        except arg_parser.ParserError:
            return
        self.fail()

    def test_parse_args_bool_specified(self):
        output = arg_parser.parse_args('+test', args_types={'test': bool})
        self.assertEqual(output, {'test': True})

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
