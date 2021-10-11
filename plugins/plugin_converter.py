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
import shlex
import typing
from types import FunctionType

try:
    # noinspection PyPackageRequirements
    import main
except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

__meta_data__ = {
    'name': 'plugin_converter',
    'commands': [
        'convert'
    ]
}

log = main.make_log_function('converter')


class Unit:
    def __init__(self, name: str, aliases: typing.Optional[typing.List[str]] = None, human_name=None):
        if aliases is None:
            aliases = []
        self.aliases = aliases
        self.name = name
        self.human_name = human_name if human_name is not None else name

    def __repr__(self):
        return f'Unit({self.name})'

    def __str__(self):
        return self.name

    def __add__(self, other):
        if isinstance(other, Unit):
            return UnitConversion(self, other)
            # return self.name + '->' + other.name
        elif isinstance(other, str):
            return self.name + other


class UnitConversion:
    def __init__(self, unit_from: Unit, unit_to: Unit):
        self.unit_from = unit_from
        self.unit_to = unit_to

    def __str__(self):
        return str(self.unit_from) + '=>' + str(self.unit_to)

    def __repr__(self):
        return f'UnitConversion({self.unit_from!r}, {self.unit_to!r})'

    def __eq__(self, other):
        if isinstance(other, UnitConversion):
            return (other.unit_from.name == self.unit_from.name
                    and other.unit_to.name == self.unit_to.name)

    def __hash__(self):
        return hash((self.unit_from.name, self.unit_to.name))


UNITS = {
}


def create_unit(name: str, aliases: typing.Optional[typing.List[str]] = None, human_name=None):
    UNITS[name] = Unit(name, aliases, human_name)
    log('info', f'Create unit {name} with aliases {aliases}')


create_unit('CELSIUS', aliases=['*c', '*C', 'c', 'C', '°c', '°C', 'celsius'], human_name='°C')
create_unit('FAHRENHEIT', aliases=['*f', '*F', 'f', 'F', '°f', '°F', 'fahrenheit'], human_name='°F')
create_unit('KELVIN', aliases=['*k', '*K', 'k', 'K', '°k', '°K', 'kelvin'], human_name='°K')

create_unit('METER', aliases=['m', 'meter', 'meters', 'metre', 'metres'], human_name='m')
create_unit('MILLIMETER', aliases=['mm', 'millimetre', 'millimeter', 'millimetres', 'millimeters'], human_name='mm')
create_unit('CENTIMETER', aliases=['cm', 'centimetre', 'centimeter', 'centimetres', 'centimeters'], human_name='cm')

# KKona
create_unit('INCH', aliases=['in', '\"', '″', 'inches', 'inch'], human_name='in')
create_unit('YARD', aliases=['yd', 'yards', 'yard'], human_name='yd')
create_unit('FOOT', aliases=['ft', 'foot', 'feet', '′'], human_name='ft')

create_unit('FREEDOM', aliases=['freedom units', 'freedom unit', '¯\\_(ツ)_/¯'], human_name='¯\\_(ツ)_/¯')
# end kkOna

CONVERSION_TABLE = {}


def convert_unit(data: int, unit_from: Unit, unit_to) -> int:
    if unit_to.name == 'FREEDOM' or unit_from.name == 'FREEDOM':  # it's a freedom conversion let the user do whatever
        return data
    conversion = unit_from + unit_to
    log('info', f'Converting {unit_from!r} to {unit_to!r} ({conversion})')
    if conversion in CONVERSION_TABLE:
        return CONVERSION_TABLE[conversion](data)
    else:
        for conv in CONVERSION_TABLE:
            print(conv, type(conv))
            if conv.unit_from == unit_from and conv.unit_from + unit_to in CONVERSION_TABLE:
                log('info', f'Using conversion from {unit_from} to {conv.unit_from} to {unit_from}')
                return convert_unit(convert_unit(data, unit_from, conv.unit_from), conv.unit_from, unit_to)
        return 'F'


def find_unit(unit_name: str) -> Unit:
    unit = None
    for i in UNITS.values():
        if unit_name == i.name:
            unit = i
            break
        if unit_name in i.aliases:
            unit = i
            break
    if unit is None:
        return UNITS['FREEDOM']
    return unit


def find_unit_with_data(data: str) -> typing.Tuple[int, Unit]:
    numbers = ''
    unit_name = ''
    for num, j in enumerate(data):
        j: str
        num: int
        if j.isnumeric():
            numbers += j
        else:
            unit_name = data[num:]
            break
    unit = find_unit(unit_name)
    return int(numbers), unit


# noinspection PyRedeclaration
CONVERSION_TABLE: typing.Dict[UnitConversion, FunctionType] = {
    UNITS['CELSIUS'] + UNITS['FAHRENHEIT']: lambda inp: inp * (9 / 5) + 32,
    UNITS['FAHRENHEIT'] + UNITS['CELSIUS']: lambda inp: (inp - 32) * 5 / 9,

    UNITS['KELVIN'] + UNITS['CELSIUS']: lambda inp: inp - 273.15,
    UNITS['CELSIUS'] + UNITS['KELVIN']: lambda inp: inp + 273.15,

    # UNITS['FAHRENHEIT'] + UNITS['KELVIN']:
    #     lambda inp: convert_unit(
    #         convert_unit(inp, UNITS['FAHRENHEIT'], UNITS['CELSIUS']),
    #         UNITS['CELSIUS'],
    #         UNITS['KELVIN']
    #     ),
    # UNITS['KELVIN'] + UNITS['FAHRENHEIT']: lambda inp: convert_unit(
    #     convert_unit(inp, UNITS['FAHRENHEIT'], UNITS['CELSIUS']),
    #     UNITS['CELSIUS'],
    #     UNITS['KELVIN']
    # ),

    UNITS['METER'] + UNITS['CENTIMETER']: lambda inp: inp * 100,
    UNITS['CENTIMETER'] + UNITS['METER']: lambda inp: inp / 100,

    UNITS['CENTIMETER'] + UNITS['MILLIMETER']: lambda inp: inp * 10,
    UNITS['MILLIMETER'] + UNITS['CENTIMETER']: lambda inp: inp / 10,

    UNITS['MILLIMETER'] + UNITS['METER']: lambda inp: inp / 1_000,
    UNITS['METER'] + UNITS['MILLIMETER']: lambda inp: inp * 1_000,

    # KKona
    UNITS['INCH'] + UNITS['MILLIMETER']: lambda inp: inp * 25.4,
    UNITS['MILLIMETER'] + UNITS['INCH']: lambda inp: inp / 25.4,

    UNITS['INCH'] + UNITS['FOOT']: lambda inp: inp / 12,
    UNITS['FOOT'] + UNITS['INCH']: lambda inp: inp * 12,

    UNITS['INCH'] + UNITS['YARD']: lambda inp: inp / 36,
    UNITS['YARD'] + UNITS['INCH']: lambda inp: inp * 36,

    # meters to millimeters to inches to feet
    UNITS['METER'] + UNITS["FOOT"]: lambda inp: inp * 1_000 / 25.4 / 12,
    UNITS['FOOT'] + UNITS['METER']: lambda inp: inp / 1_000 * 25.4 * 12,

    UNITS['CENTIMETER'] + UNITS['FOOT']: lambda inp: convert_unit(
        convert_unit(inp, UNITS['CENTIMETER'], UNITS['METER']),
        UNITS['METER'], UNITS['FOOT']
    )
}

p_conv = twitchirc.ArgumentParser(prog='!convert', add_help=False)
p_conv.add_argument('data')
p_conv.add_argument('unit_to')


@main.bot.add_command('convert')
def command_convert(msg: twitchirc.ChannelMessage):
    argv = shlex.split(main.delete_spammer_chrs(msg.text))
    if len(argv) == 1:
        return f"@{msg.user} " + p_conv.format_usage()
    args = p_conv.parse_args(argv[1:])
    if args is None:
        return f"@{msg.user} " + p_conv.format_usage()
    number, unit_from = find_unit_with_data(args.data)
    unit_to = find_unit(args.unit_to)
    converted = convert_unit(number, unit_from, unit_to)
    if converted == 'F':
        return (f'@{msg.user} Conversion is not possible: conversion '
                f'{unit_from}({unit_from.human_name}) to {unit_to}({unit_to.human_name})')
    else:
        return f'@{msg.user} {number:.2f}{unit_from.human_name} = {converted:.2f}{unit_to.human_name}'
