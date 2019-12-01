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
import json
import select
import socket
from typing import List, Tuple


class Connection:
    def __init__(self, address='ipc_server'):
        self.address = address
        self.max_recv = 8192
        self.buf = b''
        self.sock = None
        self.connect()

    def reconnect(self):
        self.sock.close()
        self.connect()

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.address)

    def command(self, command: bytes, no_reconnect=False):
        try:
            self.sock.send(command + b'\r\n')
        except BrokenPipeError:
            if no_reconnect:
                raise
            self.reconnect()
            return self.command(command, no_reconnect=True)

    def _receive(self, recv_until_complete):
        msgs = []
        if recv_until_complete:
            first = True
            while self.buf or first:
                msgs += self.decode(self.sock.recv(self.max_recv))
                first = False
        else:
            msgs += self.decode(self.sock.recv(self.max_recv))
        return msgs

    def receive(self, block: bool = True, recv_until_complete=False):
        if block:
            return self._receive(recv_until_complete)
        else:
            if select.select([self.sock], [], [], 0)[0]:
                return self._receive(recv_until_complete)
            else:
                return None

    def decode(self, data: bytes) -> List[Tuple[str, str]]:
        lines = (self.buf + data).split(b'\r\n')
        self.buf = b''
        if lines[-1] != '':
            self.buf += lines.pop()
        messages: List[Tuple[str, str]] = []
        for line in lines:
            line = line.decode('utf-8')
            if line.startswith('~~'):
                messages.append(('command_output', line[2:]))
            elif line.startswith('~'):
                messages.append(('output', line[1:]))
            elif line.startswith('!'):
                messages.append(('error', line[1:]))
            elif line.startswith('$'):
                try:
                    messages.append(('json', json.loads(line[1:])))
                except:
                    messages.append(('failed_json', line[1:]))
            else:
                messages.append(('unknown', line))
        return messages

    def close(self):
        self.command(b'quit')
        self.sock.close()
