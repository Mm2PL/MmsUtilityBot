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
import typing
import grpc
from .compiled.bot_pb2_grpc import add_BotServicer_to_server, BotServicer
from .bot_servicer import BotServiceImpl
from .. import log

server: typing.Optional[BotServicer] = None


async def init_server(listen_addresses):
    global server
    server = grpc.aio.server()
    add_BotServicer_to_server(BotServiceImpl(), server)
    # listen_addr = '[::1]:50051'
    for i in listen_addresses:
        server.add_insecure_port(i)
    log('info', f"Starting GRPC server on {', '.join(listen_addresses)}")
    await server.start()
