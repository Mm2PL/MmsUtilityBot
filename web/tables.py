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
from typing import Any, List, Tuple

from flask import escape, render_template
from markupsafe import Markup


def _format_cell_data(value) -> str:
    if isinstance(value, bool):
        return Markup(f'<div class=cell_{value}>{str(value).lower()}</div>')
    elif value is None:
        return 'N/A'
    elif isinstance(value, str):
        return escape(value)
    elif isinstance(value, (int, float)):
        return Markup(f'<div class=cell_number>{value}</div>')
    else:
        return Markup(f'<div class=cell_unknown>{escape(repr(value))}</div>')


def _custom_style_from_cell_data(value) -> str:
    if isinstance(value, bool):
        if value is True:
            return 'background-color: #00aa00;'
        else:
            return 'background-color: #aa0000;'
    else:
        return ''


def render_table(title: str, data: List[List[Any]], header: List[Tuple[str, str]], extra_markup=None):
    return render_template(
        'table_view.html',
        title=title,
        data=data,
        header=header,
        enumerate=enumerate,  # dirty hack
        _format_cell_data=_format_cell_data,
        _custom_style_from_cell_data=_custom_style_from_cell_data,
        extra_markup=extra_markup if extra_markup else Markup()
    )
