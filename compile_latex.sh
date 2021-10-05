#!/usr/bin/env bash
#
# This is a simple utility bot
# Copyright (C) 2021 Mm2PL
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
PREFIX=$(mktemp -d)
INPUT="$PREFIX"/input.tex
OUTPUT="$PREFIX"/input.pdf
PNG_PATH="$PREFIX/output.png"

echo "$PREFIX"
chmod 777 "$PREFIX"

cat > "$INPUT"

xelatex -output-directory "$PREFIX" "$INPUT" || exit 1
pdftoppm -png "$OUTPUT" -r 600 > "$PNG_PATH" || exit 2
