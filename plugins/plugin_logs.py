#  This is a simple utility bot
#  Copyright (C) 2019 Mm2PL
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
import queue
import threading
import time
import typing

import regex

import plugins.models.logentry as logentry_model
from plugins.models.logentry import CAUSE_TASK, CAUSE_OTHER

try:
    # noinspection PyPackageRequirements
    import main

except ImportError:
    import util_bot as main

    exit()
# noinspection PyUnresolvedReferences
import twitchirc

NAME = 'logs'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
    ]
}
_print = print
log = main.make_log_function(NAME)
LogEntry = logentry_model.get(main.Base)


class Logger:
    def __init__(self, source, parent):
        self.source = source
        self.parent: 'Plugin' = parent

    def log(self, level, message, cause=CAUSE_OTHER):
        return self.parent.log(self.source, level, message, cause=cause)

    def __call__(self, level, *message, cause=CAUSE_OTHER):
        self.log(level, ' '.join([str(i) for i in message]), cause)


class Plugin(main.Plugin):
    CAUSE_COMMAND = 0
    CAUSE_TASK = 1
    CAUSE_API = 2
    CAUSE_OTHER = 3

    def __init__(self, module, source):
        super().__init__(module, source)
        self.log_levels = {
            'debug': -1,
            'info': 0,
            'warn': 1,
            'WARN': 2,
            'err': 3,
            'fat': 10
        }
        self.log_level = self.log_levels['debug']
        self.db_log_level = self.log_levels['info']
        self._logger_queue = queue.Queue()
        self._logger_thread = threading.Thread(target=self._logger_thread_func, args=(self._logger_queue,),
                                               daemon=True)
        self._logger_thread.start()
        self._logger_thread_stop_lock = threading.Lock()
        self.oauth_pat = regex.compile(
            'oauth:[a-z0-9]{30}'
        )
        self._patch_main()
        self._register_atexit()

    def _patch_main(self):
        main.make_log_function = self.create_logger
        main.log = self.create_logger('main')
        main.print = lambda *args, **kwargs: main.log('info', *args, **kwargs)

    @property
    def no_reload(self):
        return True

    @property
    def name(self) -> str:
        return NAME

    @property
    def commands(self) -> typing.List[str]:
        return []

    def on_reload(self):
        print('on reload/exit')
        try:
            self._logger_thread_stop_lock.acquire()
            self._logger_queue.put(None)
            self._print_log('logs',
                            0,
                            'Stopping logging...',
                            cause=CAUSE_OTHER)
            self._logger_thread.join()
        except:
            pass

    def _db_log(self, source: str, level: int, message: str, cause):
        if self.db_log_level <= level:
            self._logger_queue.put(
                {
                    'source': source,
                    'level': level,
                    'message': message,
                    'cause': cause
                }
            )

    def _translate_level(self, level):
        if isinstance(level, int):
            return level
        else:
            return self.log_levels[level]

    def log(self, source: str, level: typing.Union[str, int], *message, cause=CAUSE_OTHER):
        msg = self.oauth_pat.sub('[OAUTH TOKEN]', '  '.join([str(i) for i in message]))
        self._db_log(source, self._translate_level(level), msg, cause)
        self._print_log(source, self._translate_level(level), msg, cause)

    def create_logger(self, source):
        logger = Logger(source, self)
        logger.log('debug', 'Initialized logger.', cause=CAUSE_TASK)
        return logger

    # noinspection PyMethodMayBeStatic
    def _flush_batch(self, batch):
        _print('Flushing batch...')
        with main.session_scope_local_thread() as session:
            for obj in batch:
                session.add(LogEntry(**obj))
        _print('Flushing done...')

    def _logger_thread_func(self, q: queue.Queue):
        _print('Started logging...')
        batch = [
            {
                'source': 'logs',
                'level': -1,
                'message': 'Started logging.',

                'cause': CAUSE_TASK
            }
        ]
        batch_start = time.time()
        while 1:
            data = q.get()
            if self._logger_thread_stop_lock.locked() or data is None:
                print('t: stop!')
                if batch:
                    self._flush_batch(batch)
                return
            batch.append(data)
            if len(batch) > 50 or time.time() > batch_start + 30:
                self._flush_batch(batch)
                batch = []
                batch_start = time.time()

    def _print_log(self, source, level, message, cause):
        if self.log_level <= level:
            _print(LogEntry.static_pretty(source, level, message, cause))

    def _register_atexit(self):
        def write_post_dis_conn(*args):
            del args
            self.log('logs',
                     0,
                     'Disconnected!',
                     cause=CAUSE_TASK)

        main.bot.handlers['post_disconnect'].append(write_post_dis_conn)
