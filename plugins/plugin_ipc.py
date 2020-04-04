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

# noinspection PyUnresolvedReferences
import io
import json
import os
import queue
import select
import socket
import threading
import typing
import uuid
import re
import traceback
from typing import Dict

import twitchirc
from twitchirc import Event

try:
    import main
except ImportError:
    import util_bot as main

    exit()
try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    if typing.TYPE_CHECKING:
        import plugins.plugin_manager as plugin_manager
    else:
        raise
__meta_data__ = {
    'name': 'plugin_ipc',
    'commands': []
}


class ListDict(dict):
    def __init__(self):
        super().__init__()
        self.last_id = -1

    def append(self, obj):
        self.last_id += 1
        self[self.last_id] = obj


log = main.make_log_function('plugin_ipc')
commands: typing.Dict[str, typing.Callable[[socket.socket, str, int], str]] = {}
sockets: ListDict = ListDict()

server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
if os.path.isfile('./ipc_server'):
    os.unlink('./ipc_server')
server_socket.bind('./ipc_server')
server_socket.listen(0)

_old_send = main.bot.send


def send_msg_to_socket(sock_id, msg):
    if sock_id in sockets:
        sockets[sock_id].send(f'~~{msg.text}\r\n'.encode('utf-8'))
    else:
        log('warn', 'Cannot send message to deleted connection. Happened here:')
        st = traceback.format_stack(limit=100)
        for i in ''.join(st).split('\n'):
            log('warn', i)


class IPCMiddleware(twitchirc.AbstractMiddleware):
    def send(self, event: Event) -> None:
        msg: typing.Union[str, bytes, twitchirc.Message] = event.data['message']
        queue: typing.Optional[str] = event.data['queue'] if 'queue' in event.data else None
        if isinstance(msg, twitchirc.ChannelMessage):
            m = re.match(r'__IPC ([0-9]+)', msg.channel)
            if m:
                event.cancel()
                send_msg_to_socket(int(m.group(1)), msg)
            else:
                return

    def receive(self, event: Event) -> None:
        pass

    def command(self, event: Event) -> None:
        pass

    def permission_check(self, event: Event) -> None:
        pass

    def join(self, event: Event) -> None:
        pass

    def part(self, event: Event) -> None:
        pass

    def disconnect(self, event: Event) -> None:
        pass

    def connect(self, event: Event) -> None:
        pass

    def add_command(self, event: Event) -> None:
        pass


main.bot.middleware.append(IPCMiddleware())


# def new_send(message: typing.Union[str, twitchirc.ChannelMessage], queue='misc') -> None:
#     if isinstance(message, twitchirc.ChannelMessage) and (message.user.startswith('__IPC ')
#                                                           or message.channel.startswith('__IPC ')):
#         print(message)
#         sock_id = int(message.channel.split(' ', 1)[1])
#         if sock_id in sockets:
#             sockets[sock_id].send(('~~' + message.text).encode('utf-8'))
#         else:
#             return  # socket was closed.
#     else:
#         return  # _old_send(message, queue)
#
#
# main.bot.send = new_send
#
#
def add_command(command_name):
    def decorator(func):
        commands[command_name.lower()] = func
        log('debug', f'Add command {command_name} with function {func}')
        return func

    return decorator


def _purge_closed():
    global sockets
    for k, v in sockets.copy().items():
        v: socket.socket
        if v.fileno() == -1:
            del sockets[k]
            del response_write_queues[k]


msg_buffer: Dict[int, bytes] = {
}
response_write_queues: Dict[int, queue.Queue] = {

}


def _find_message(sock_id):
    print(sock_id, msg_buffer[sock_id])
    if b'\r\n' in msg_buffer[sock_id]:
        p_1, p_2 = msg_buffer[sock_id].split(b'\r\n', 1)
        msg_buffer[sock_id] = p_2
        return p_1
    return None


def format_json(data) -> bytes:
    return (f'$' + json.dumps(data) + '\r\n').encode('utf-8')


def _check_for_messages():
    global sockets
    _purge_closed()
    read_ready, _, _ = select.select(sockets.values(), [], [], 0)
    if read_ready:
        for sock in read_ready:
            msg: bytes = sock.recv(8_192)
            sock_id = _get_sock_id(sock)

            if sock_id == -1:
                raise main.WayTooDank('weee woo')
            if msg == b'':
                log('debug', f'Auto-close bad connection {sock_id}')
                sock.close()
                if sock_id in sockets:
                    del sockets[sock_id]
                return
            if sock_id in msg_buffer:
                msg_buffer[sock_id] += msg
            else:
                msg_buffer[sock_id] = msg
            message = _find_message(sock_id)
            if message is not None:
                on_receive_message(sock, message, sock_id)


def _get_sock_id(sock):
    for k, s in sockets.items():
        if sock is s:
            return k
    return -1


def on_receive_message(sock: socket.socket, msg: bytes, sock_id):
    print(f'Recv message {msg}')
    if sock_id == -1:
        log('err', 'How did this happen?\n'
                   'Received message from socket with no internal id.')
        log('warn', traceback.format_stack())
        return

    msg: str = msg.decode('utf-8')
    cmd = msg.split(' ', 1)
    print(repr(cmd), repr(cmd[0].lower()), commands)
    if cmd[0].lower() in commands:
        print(f'TRIGGER COMMAND {cmd[0]} with args: {cmd!r}')
        try:
            result = commands[cmd[0].lower()](sock, msg, sock_id)
        except:
            for i in ''.join(traceback.format_stack(1000)).split('\n'):
                log('warn', i)

            result = (b'!-500\r\n'
                      b'~Internal error\r\n'
                      +
                      format_json({
                          'type': 'error',
                          'message': 'Internal error',
                          'source': 'command_handler'
                      }))

        if isinstance(result, str):
            sock.send(result.encode('utf-8'))
        elif isinstance(result, bytes):
            sock.send(result)
    else:
        sock.send((b'!1\r\n~No command\r\n'
                   +
                   format_json({
                       'type': 'error',
                       'message': 'No command',
                       'source': 'command_handler'
                   })))


def _check_for_new_connections():
    read_ready, _, _ = select.select([server_socket], [], [], 0)
    if read_ready:
        sock, ip = server_socket.accept()
        sockets.append(sock)
        print(f'Accepted connection for {ip}. Sock id {sockets.last_id}')
        response_write_queues[sockets.last_id] = queue.Queue()
        sock.send(f'~Welcome to the Mm\'s Utility bot IPC interface.\r\n'.encode('utf-8'))
        sock.send(f'~You have logged in with ID {sockets.last_id}\r\n'.encode('utf-8'))
        sock.send(format_json({
            'type': 'login/your_id',
            'id': sockets.last_id,
            'source': 'login_burst'
        }))


def _write_queued_messages():
    for sid, q in response_write_queues.items():
        while not q.empty():
            task = q.get(False)
            log('debug', f'Write message {task} to socket {sid}')
            sockets[sid].send(task)
            q.task_done()
            log('debug', f'Done.')


def on_timer_hit():
    try:
        _check_for_new_connections()
        _check_for_messages()
        _write_queued_messages()
    except:
        log('err', traceback.format_exc())


main.bot.schedule_repeated_event(0.1, 5, on_timer_hit, (), {})


# basic commands:

@add_command('run')
def _command_run(sock: socket.socket, msg: str, socket_id):
    text = msg.split(' ', 1)[1]
    message = twitchirc.ChannelMessage(channel=f'__IPC {socket_id}',
                                       text=text,
                                       user=f'__IPC {socket_id}')
    message.flags = {
        'badge-info': '',
        'badges': ['broadcaster/1'],
        'color': '#ffffff',
        'display-name': f'__IPC_Socket_id_{socket_id}',
        'id': str(uuid.uuid4()),
        'room-id': socket_id + 1000,
        'user-id': socket_id + 1000,
        'turbo': '0',
        'subscriber': '0',
        'emotes': ''
    }
    # noinspection PyProtectedMember
    main.bot._call_command_handlers(message)
    return f'~Sent: {text} as {message.user!r}\r\n'.encode('utf-8')


@add_command('quit')
def _command_quit(sock: socket.socket, msg: str, socket_id):
    global sockets, msg_buffer
    log('debug', f'Closed connection {socket_id} by request.')
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()
    if socket_id in sockets:
        del sockets[socket_id]
    if socket_id in msg_buffer:
        del msg_buffer[socket_id]
    return None


@add_command('get_user_alias')
def _command_get_user_alias(sock: socket.socket, msg: str, socket_id):
    arg: str
    _, arg = msg.replace('\n', '').replace('\r\n', '').split(' ', 1)
    if arg.isnumeric():
        user_id = int(arg)

        def _fetch_user(rwq):
            u = main.User.get_by_local_id(user_id)
            if u is None:
                rwq.put(
                    b'!2\r\n'
                    b'~A user with this ID doesn\'t exist.'
                    +
                    format_json({
                        'type': 'error',
                        'source': 'get_user_alias',
                        'message': 'A user with this ID doesn\'t exist.'
                    }))
            else:
                rwq.put(format_json({
                    'type': 'user_fetch',
                    'source': 'get_user_alias',
                    'id': u.id,
                    'mod_in': u.mod_in,
                    'sub_in': u.sub_in,
                    'twitch_id': u.twitch_id,
                    'username': u.last_known_username,
                }))

        t = threading.Thread(target=_fetch_user, args=(response_write_queues[socket_id],))
        t.start()
    else:
        return (b'!1\r\n'
                b'~Bad user id\r\n'
                +
                format_json({
                    'type': 'error',
                    'source': 'get_user_alias',
                    'message': 'Bad user id.'
                }))


@add_command('get_user_id')
def _command_get_user_id(sock: socket.socket, msg: str, socket_id):
    arg: str
    _, arg = msg.replace('\n', '').replace('\r\n', '').split(' ', 1)
    if arg.isnumeric():
        user_id = int(arg)

        def _fetch_user(rwq):
            u = main.User.get_by_twitch_id(user_id)
            if u is None:
                rwq.put(
                    b'!2\r\n'
                    b'~A user with this ID is not known to this bot.'
                    +
                    format_json({
                        'type': 'error',
                        'source': 'get_user_id',
                        'message': 'A user with this ID is not known to this bot.'
                    }))
            else:
                rwq.put(format_json({
                    'type': 'user_fetch',
                    'source': 'get_user_id',
                    'id': u.id,
                    'mod_in': u.mod_in,
                    'sub_in': u.sub_in,
                    'twitch_id': u.twitch_id,
                    'username': u.last_known_username,
                }))

        t = threading.Thread(target=_fetch_user, args=(response_write_queues[socket_id],))
        t.start()
    else:
        return (b'!1\r\n'
                b'~Bad user id\r\n'
                +
                format_json({
                    'type': 'error',
                    'source': 'get_user_id',
                    'message': 'Bad user id.'
                }))


@add_command('get_user_name')
def _command_get_user_name(sock: socket.socket, msg: str, socket_id):
    arg: str
    _, arg = msg.replace('\n', '').replace('\r\n', '').split(' ', 1)

    def _fetch_user(rwq):
        u = main.User.get_by_name(arg)
        if len(u) == 0:
            rwq.put(
                b'!2\r\n'
                b'~A user with this ID is not known to this bot.'
                +
                format_json({
                    'type': 'error',
                    'source': 'get_user_name',
                    'message': 'A user with this ID is not known to this bot.'
                }))
        elif len(u) > 1:
            rwq.put(format_json({
                'type': 'user_fetch',
                'source': 'get_user_name',
                'multiple': [
                    {
                        'id': user.id,
                        'mod_in': user.mod_in,
                        'sub_in': user.sub_in,
                        'twitch_id': user.twitch_id,
                        'username': user.last_known_username
                    }
                    for user in u
                ]
            }))
        else:
            u = u[0]
            rwq.put(format_json({
                'type': 'user_fetch',
                'source': 'get_user_name',
                'id': u.id,
                'mod_in': u.mod_in,
                'sub_in': u.sub_in,
                'twitch_id': u.twitch_id,
                'username': u.last_known_username,
            }))

    t = threading.Thread(target=_fetch_user, args=(response_write_queues[socket_id],))
    t.start()


@add_command('reload_settings')
def _command_reload_settings(sock: socket.socket, msg: str, socket_id):
    _, channel = msg.replace('\n', '').replace('\r\n', '').split(' ', 1)
    channel = int(channel)
    print(_, channel)
    if channel != -1:
        user = main.User.get_by_local_id(channel)
        print(user, user.last_known_username)
        if user.last_known_username not in plugin_manager.channel_settings:
            response_write_queues[socket_id].put(
                b'!2\r\n'
                b'~A user with this ID is not known to this bot.\r\n'
                +
                format_json({
                    'type': 'error',
                    'source': 'reload_settings',
                    'message': 'A user with this ID is not known to this bot.'
                })
            )
        else:
            print(f'update settings for {channel!r} (#{user.last_known_username!r})')
            del plugin_manager.channel_settings[user.last_known_username]
            with main.session_scope() as session:
                settings = (session.query(plugin_manager.ChannelSettings)
                            .filter(plugin_manager.ChannelSettings.channel_alias == user.id)
                            .first())
                plugin_manager.channel_settings[user.last_known_username] = settings
            response_write_queues[socket_id].put(
                format_json({
                    'type': 'reload_update',
                    'source': 'reload_settings',
                    'message': 'Reloaded settings for channel!'
                })
            )
    else:
        print(f'update settings for {channel!r} (GLOBAL)')
        del plugin_manager.channel_settings['GLOBAL']
        with main.session_scope() as session:
            settings = (session.query(plugin_manager.ChannelSettings)
                        .filter(plugin_manager.ChannelSettings.channel_alias == -1)
                        .first())
            plugin_manager.channel_settings['GLOBAL'] = settings
        response_write_queues[socket_id].put(
            format_json({
                'type': 'reload_update',
                'source': 'reload_settings',
                'message': 'Reloaded settings for channel!'
            })
        )


@add_command('all_settings')
def _command_all_settings(sock: socket.socket, msg: str, socket_id):
    print('pepega all settings')
    return format_json({
        'type': 'all_settings',
        'source': 'all_settings',
        'data': {
            k: {
                'owner_name': v.owner.name,
                'name': v.name,
                'default_value': '...' if v.default_value is ... else v.default_value,
                'scope': v.scope.name,
                'write_defaults': v.write_defaults,
                'setting_type': v.setting_type.__name__ if hasattr(v.setting_type, '__name__') else str(v.setting_type),
                'help': v.help
            } for k, v in plugin_manager.all_settings.items()
        }
    })


print(commands)
