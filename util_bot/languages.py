#  This is a simple utility bot
#  Copyright (C) 2021 Mm2PL
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
import dataclasses
import json
from typing import Union, List, Optional


@dataclasses.dataclass
class LanguageName:
    long: str
    short: str

    @classmethod
    def from_json(cls, data):
        return cls(
            long=data['long'],
            short=data['short']
        )


@dataclasses.dataclass
class LanguageNameData:
    native: LanguageName
    english: LanguageName
    transliterations: List[str]
    other: List[str]

    @classmethod
    def from_json(cls, data):
        return cls(
            native=LanguageName.from_json(data['native']),
            english=LanguageName.from_json(data['english']),
            transliterations=data['transliterations'],
            other=data['other']
        )

    def matches(self, specifier: str) -> bool:
        specifier = specifier.lower()
        for i in (self.native, self.english):
            if i.long.lower() == specifier:
                return True
            if i.short.lower() == specifier:
                return True
        if specifier in self.transliterations:
            return True
        if specifier in self.other:
            return True

        return False


@dataclasses.dataclass
class LanguageData:
    name: Optional[str]
    group: str
    names: Union[List[str], LanguageNameData]
    iso6391: str
    iso6392: str
    iso6393: str
    glottolog: Optional[str]

    @classmethod
    def from_json(cls, data):
        names = data['names']
        if isinstance(names, dict):
            names = LanguageNameData.from_json(names)
        return cls(
            name=data.get('name'),
            group=data['group'],
            names=names,
            iso6391=data['iso6391'],
            iso6392=data['iso6392'],
            iso6393=data['iso6393'],
            glottolog=data.get('glottolog')
        )

    def matches(self, specifier: str) -> bool:
        specifier = specifier.lower()
        if self.name and specifier == self.name.lower():
            return True
        if isinstance(self.names, list) and specifier in map(lambda s: s.lower(), self.names):
            return True
        if isinstance(self.names, LanguageNameData) and self.names.matches(specifier):
            return True
        if (self.iso6391 and specifier == self.iso6391.lower()
                or self.iso6392 and specifier == self.iso6392.lower()
                or self.iso6393 and specifier == self.iso6393.lower()):
            return True
        if self.glottolog and specifier == self.glottolog.lower():
            return True
        return False

    @classmethod
    def get_by_name_or_code(cls, inp: str) -> Optional['LanguageData']:
        for i in languages:
            if i.matches(inp):
                return i
        return None


languages: Optional[List[LanguageData]] = None


def _parse_data(data):
    global languages
    languages = list(map(LanguageData.from_json, data))
    return languages


def load_data():
    with open('languages.json', 'r') as f:
        d = json.load(f)
    _parse_data(d)
