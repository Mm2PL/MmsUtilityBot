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
import asyncio
import typing
import math
import io

from PIL import Image, ImageOps
import requests

C_SIZE = 2048

SIZE_LIMIT = 10_000_000
POSITIONS = [
    0x1,
    0x8,
    0x2,
    0x10,
    0x4,
    0x20,
    0x40,
    0x80
]


async def to_braille_from_url(image_url: str, reverse: bool = False, size_percent: typing.Optional[float] = None,
                              max_x: typing.Optional[int] = None, max_y: typing.Optional[int] = None,
                              sensitivity: typing.Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.5),
                              enable_padding=True, pad_size=(60, 60)):
    if size_percent is None and max_x is None and max_y is None:
        raise RuntimeError('You have to specify either size_percent, max_x or max_y for to_braille to work.')
    r = requests.get(image_url, stream=True)

    if int(r.headers.get('Content-Length')) > SIZE_LIMIT:  # 10M
        raise ValueError('Response is over the size limit.')
    img_data = io.BytesIO()
    num = 0
    for c in r.iter_content(C_SIZE):
        num += 1
        img_data.write(c)
        if C_SIZE * num > SIZE_LIMIT:
            raise ValueError('Response is over the size limit.')

    img = Image.open(img_data)
    return await to_braille_from_image(img, reverse=reverse, size_percent=size_percent, max_x=max_x, max_y=max_y,
                                       sensitivity=sensitivity, enable_padding=enable_padding, pad_size=pad_size)


async def to_braille_from_image(img: Image, reverse: bool = False, size_percent: typing.Optional[float] = None,
                                max_x: typing.Optional[int] = None, max_y: typing.Optional[int] = None,
                                sensitivity: typing.Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.5),
                                enable_padding=True, pad_size=(60, 60)):
    """this function should be run in a separate thread not to take a long time."""
    if size_percent is None and max_x is None and max_y is None:
        raise RuntimeError('You have to specify either size_percent, max_x or max_y for to_braille to work.')
    output: str = ''

    org_size = (img.width, img.height)
    img = img.convert('RGBA')
    await asyncio.sleep(0)
    if size_percent is None:
        img.thumbnail((max_x, max_y))
    else:
        new_size = (org_size[0] * (size_percent / 100), org_size[1] * (size_percent / 100))
        if size_percent > 100:
            img = img.resize((round(new_size[0]), round(new_size[1])))
        else:
            img.thumbnail(new_size)
    await asyncio.sleep(0)
    percent_area = ((img.width * img.height)
                    / (org_size[0] * org_size[1])
                    * 100)
    percent_x = (img.width / org_size[0] * 100)
    percent_y = (img.height / org_size[1] * 100)
    if enable_padding:
        expand_size = (pad_size[0] - img.size[0], pad_size[1] - img.size[1])
        if expand_size[0] < 0:
            expand_size = (0, expand_size[1])
        if expand_size[1] < 0:
            expand_size = (expand_size[0], 0)
        print(expand_size)
        img = ImageOps.expand(img, expand_size)
        output += (f'Converted image to {img.width}X{img.height} or {percent_area:.2f}% area, '
                   f'{percent_x:.2f}% of X, {percent_y:.2f}% of Y of the original size. Added padding of '
                   f'{"x".join([str(i) for i in expand_size])} pixels\n')
        await asyncio.sleep(0)
    else:
        output += (f'Converted image to {img.width}X{img.height} or {percent_area:.2f}% area, '
                   f'{percent_x:.2f}% of X, {percent_y:.2f}% of Y of the original size.\n')

    real_y = 0

    def _get_pixel(coords):
        if coords[0] >= img.width or coords[1] >= img.height:
            return 0, 0
        else:
            data = img.getpixel(coords)
            return data

    for _ in range(math.floor(img.height / 4)):  # iterate through every fourth line. ⣿
        real_x = 0
        if real_x % 10 == 0:
            await asyncio.sleep(0)
        for _ in range(math.floor(img.width / 2)):  # iterate through ever second pixel.
            # dank memory saving trick.
            # collect the pixels into a small array.
            p = [
                _get_pixel((real_x, real_y)),
                _get_pixel((real_x + 1, real_y)),

                _get_pixel((real_x, real_y + 1)),
                _get_pixel((real_x + 1, real_y + 1)),

                _get_pixel((real_x, real_y + 2)),
                _get_pixel((real_x + 1, real_y + 2)),

                _get_pixel((real_x, real_y + 3)),
                _get_pixel((real_x + 1, real_y + 3))
            ]

            character = 0x2800  # static Braille offset.

            for table_offset, pixel in enumerate(p):
                color_binary = []
                for color_num, color in enumerate(pixel):
                    color_binary.append(color > (255 / sensitivity[color_num]))
                binary = bool(sum(color_binary))  # False will result in a 0, True in a 1, numbers > 0 are truthy.
                del color_binary

                if reverse and not binary or (not reverse and binary):
                    character += POSITIONS[table_offset]
            output += chr(character)
            real_x += 2
        real_y += 4
        output += '\n'
    return output
