#  This is a simple utility bot
#  Copyright (C) 2020 Mm2PL
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
import asyncio
import functools
import io
import math
import operator
import ast
# noinspection PyUnresolvedReferences
import os
import random
import shlex
import shutil
import subprocess
import sys
import traceback
import typing

import aiohttp
import matplotlib

from plugins.models.logentry import CAUSE_COMMAND
from plugins.utils import arg_parser
from util_bot.msg import StandardizedMessage

RESULT_TOO_BIG = 'result might be too big.'

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy

# noinspection PyUnresolvedReferences
import twitchirc

import util_bot

util_bot.load_file('plugins/plugin_help.py')
try:
    import plugin_plugin_help as plugin_help
except ImportError:
    if typing.TYPE_CHECKING:
        import plugins.plugin_help as plugin_help
    else:
        raise
try:
    import plugin_chat_cache
except ImportError:
    if typing.TYPE_CHECKING:
        import plugins.plugin_chat_cache as _plugin_chat_cache

        plugin_chat_cache: _plugin_chat_cache.Plugin
    else:
        raise

try:
    import plugin_plugin_manager as plugin_manager
except ImportError:
    import plugins.plugin_manager as plugin_manager

util_bot.load_file('plugins/plugin_hastebin.py')
try:
    import plugin_hastebin
except ImportError:
    from plugins.plugin_hastebin import Plugin as PluginHastebin

    plugin_hastebin: PluginHastebin

NAME = 'plot'
__meta_data__ = {
    'name': f'plugin_{NAME}',
    'commands': [
        'plot'
    ]
}
log = util_bot.make_log_function(NAME)


class Context:
    source_message: StandardizedMessage
    source: str


class Plot:
    image: io.BytesIO
    steps_taken: int

    def __init__(self, image, steps_taken):
        self.image = image
        self.steps_taken = steps_taken


class FunctionWithCtx:
    def __init__(self, func):
        self.func = func
        self.__doc__ = func.__doc__

    def __call__(self, *args, ctx, **kwargs):
        return self.func(*args, ctx=ctx, **kwargs)


def _raise_from_eval(exc: Exception) -> typing.NoReturn:
    exc.from_eval = True
    raise exc


def _call(f: typing.Union[typing.Callable, ast.Lambda], *args, ctx, **kwargs) -> typing.Any:
    if isinstance(f, ast.Lambda):
        # return Math.eval_(f.body, locals_=kwargs)
        call = ast.Call(
            func=f,
            args=[
                ast.Constant(i) for i in args
            ],
            keywords=[
                ast.keyword(arg=k, value=ast.Constant(v))
                for k, v in kwargs
            ])
        return Math.call_lambda(call, {}, ctx)
    else:
        return f(*args, **kwargs)


def _function_name(f: typing.Union[ast.Lambda, typing.Callable], ctx_, start, end, step) -> typing.Optional[str]:
    if isinstance(f, typing.Callable):
        return f'{f.__name__} from {start} to {end} (in {step} increments)'
    elif isinstance(f, ast.Lambda):
        return None
    else:
        raise RuntimeError(f'Tried to check function name of object type: {type(f)!r}')


PLOT_FORMATS = [
    '-b',
    '-g',
    '-r',
    '-c',
    '-m',
    '-y',
    '-k',

    '--b',
    '--g',
    '--r',
    '--c',
    '--m',
    '--y',
    '--k'
]


@FunctionWithCtx
def _plot(function: typing.Union[ast.Lambda, typing.Callable], start: float, end: float, step: float, ctx: Context):
    return _plots([function], start, end, step, ctx=ctx)


def _set_plot_spines(axis, start, end, y_min, y_max):
    axis.spines['left'].set_position('zero')
    axis.spines['right'].set_color('none')
    axis.spines['bottom'].set_position('zero')
    axis.spines['top'].set_color('none')
    # axis.spines['left'].set_smart_bounds(True)
    # axis.spines['bottom'].set_smart_bounds(True)
    axis.spines['left'].set_bounds(y_min, y_max)
    axis.spines['bottom'].set_bounds(start, end)
    axis.xaxis.set_ticks_position('bottom')
    axis.yaxis.set_ticks_position('left')


def _export_fig(figure, steps_taken) -> Plot:
    bio = io.BytesIO()
    figure.savefig(bio, format='png')
    bio.seek(0)
    return Plot(bio, steps_taken)


MAX_STEPS = 400_000


@FunctionWithCtx
def _plots(functions: typing.List[typing.Union[ast.Lambda, typing.Callable]], start: float, end: float, step: float,
           ctx: Context):
    for num, f in enumerate(functions):
        if not isinstance(f, (ast.Lambda, typing.Callable)):
            _raise_from_eval(RuntimeError(f'(functions[{num}]) '
                                          f'Cannot use {f!r} as a function for plotting. '
                                          f'Did you want "lambda x: {f!r}"?'))
    steps_needed_to_render = int(len(functions) * (
            (end - start) / step
    ))
    if steps_needed_to_render >= MAX_STEPS:
        _raise_from_eval(
            ValueError(f'Cannot use more than {MAX_STEPS} steps, your figure would need {steps_needed_to_render}. '
                       f'Lower the accuracy or render less functions at the same time.')
        )
    figure, axis = plt.subplots(1, 1)
    fns = []
    for f in functions:
        fns.append(_function_name(f, ctx, start, end, step))

    if all(fns):
        axis.set_title('\n'.join(fns))
    else:
        title = ctx.source
        if '\n' in title:
            title = title.replace('\n', ' ')

        while '  ' in title:
            title = title.replace('  ', ' ')

        if len(title) > 200:
            title = f'{ctx.source_message.user}\'s plot'
        axis.set_title(title)

    x = numpy.arange(start, end, step)
    ys = []
    for num, f in enumerate(functions):
        y = [
            _call(f, x_coord, ctx=ctx)
            for x_coord in x
        ]
        ys.append(y)
        axis.plot(
            x,
            y,
            PLOT_FORMATS[num]
        )

    reduced = functools.reduce(operator.iconcat, ys, [])
    _set_plot_spines(axis, start, end, min(reduced), max(reduced))

    return _export_fig(figure, steps_needed_to_render)


class Helper(FunctionWithCtx):
    """
    Returns help for the object specified

    help(obj: object) -> str
    How this works:
        1. Try to lookup __doc__ for the object provided (obj.__doc__), if something was found, return it
        2. Try to lookup __doc__ for the type of that object (type(obj).__doc__), if something was found, return it,
        3. Give up.
    """

    def __repr__(self):
        return 'See help(help).'

    # noinspection PyMethodOverriding
    def __call__(self, obj: object, ctx: Context):
        if hasattr(obj, '__doc__') and obj.__doc__ is not None:
            return obj.__doc__
        elif hasattr(type(obj), '__doc__') and type(obj).__doc__ is not None:
            return type(obj).__doc__
        else:
            return 'Don\'t know how to help'

    def __init__(self):
        super().__init__(None)


class UnsafeError(Exception):
    def __repr__(self):
        return f'Possibly unsafe operation. {self.message}'

    def __init__(self, message: str):
        self.message = message


class Math:
    """
    Taken from https://github.com/pajbot/pajbot/blob/master/pajbot/modules/math.py#L134
    modified to support lambdas and other things

    Original from: http://stackoverflow.com/a/9558001
    """

    MAX_MULT = 1_000_000_000
    MAX_SHIFT = 1_000_000
    MAX_POW = 1_000
    # supported operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.BitXor: operator.xor,
        ast.USub: operator.neg,
        ast.RShift: operator.rshift,
        ast.LShift: operator.lshift,
        ast.BitAnd: operator.and_,
        ast.BitOr: operator.or_,
        ast.MatMult: operator.matmul,
        ast.Mod: operator.mod
    }
    functions = {
        'plot': _plot,
        'plots': _plots,
        'help': Helper(),

        'ceil': math.ceil,
        'comb': math.copysign,
        'fabs': math.fabs,
        'floor': math.floor,
        'fsum': math.fsum,
        'gcd': math.gcd,
        'isclose': math.isclose,
        'isfinite': math.isfinite,
        'isinf': math.isinf,
        'isnan': math.isnan,
        'ldexp': math.ldexp,
        'frexp': math.frexp,
        'modf': math.modf,
        'remainder': math.remainder,
        'trunc': math.trunc,
        'exp': math.exp,
        'expm1': math.expm1,
        'log': math.log,
        'log1p': math.log1p,
        'log2': math.log2,
        'log10': math.log10,
        'pow': math.pow,
        'sqrt': math.sqrt,
        'acos': math.acos,
        'asin': math.asin,
        'atan': math.atan,
        'atan2': math.atan2,
        'cos': math.cos,
        'hypot': math.hypot,
        'sin': math.sin,
        'degrees': math.degrees,
        'radians': math.radians,
        'acosh': math.acosh,
        'asinh': math.asinh,
        'atanh': math.atanh,
        'cosh': math.cosh,
        'sinh': math.sinh,
        'tanh': math.tanh,
        'erf': math.erf,
        'erfc': math.erfc,
        'gamma': math.gamma,
        'lgamma': math.lgamma,

        'int': int,
        'float': float,
        'str': str,
        'abs': abs,
        'min': min,
        'max': max,
        'len': len
    }
    default_locals = {
        'pi': math.pi,
        'π': math.pi,
        'e': math.e,
        'tau': math.tau,
        'τ': math.tau,
        'inf': math.inf,
        'nan': math.nan
    }

    @staticmethod
    def eval_expr(expr, ctx):
        """
        >>> Math.eval_expr('2^6')
        4
        >>> Math.eval_expr('2**6')
        64
        >>> Math.eval_expr('1 + 2*3**(4^5) / (6 + -7)')
        -5.0
        """
        try:
            return Math.nice_result(Math.eval_(ast.parse(expr, mode="eval").body, {}, ctx))
        except SyntaxError as e:
            _raise_from_eval(e)

    @staticmethod
    def nice_result(node):
        if isinstance(node, ast.Lambda):
            return '<Anonymous function>'
        elif isinstance(node, Plot):
            return node
        else:
            return str(node)

    @staticmethod
    def check_safe(node, opargs) -> typing.Tuple[bool, str]:
        not_all_numbers = any((not isinstance(i, (int, float)) for i in opargs))
        if not_all_numbers:
            return True, 'ok'

        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Mult):
                bigger = max(opargs)
                if bigger > Math.MAX_MULT:
                    return False, RESULT_TOO_BIG
            elif isinstance(node.op, ast.Pow):
                _, right = opargs
                if right > Math.MAX_POW:
                    return False, RESULT_TOO_BIG
            elif isinstance(node.op, ast.LShift):
                left, right = opargs

                if right >= Math.MAX_SHIFT or left >= Math.MAX_MULT:
                    return False, RESULT_TOO_BIG
            elif isinstance(node.op, ast.Div):
                smaller = max(opargs)
                if smaller < 1:
                    if (1 / smaller) >= Math.MAX_MULT:
                        return False, RESULT_TOO_BIG

        return True, 'ok'

    @staticmethod
    def eval_(node, locals_, ctx):
        if locals_ is None:
            locals_ = {}

        if isinstance(node, ast.Num):  # <number>
            return node.n
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Tuple):
            return tuple(
                (Math.eval_(i, locals_, ctx) for i in node.elts)
            )
        elif isinstance(node, ast.List):
            return list(
                (Math.eval_(i, locals_, ctx) for i in node.elts)
            )
        elif isinstance(node, ast.Set):
            return set(
                (Math.eval_(i, locals_, ctx) for i in node.elts)
            )
        elif isinstance(node, ast.Name):
            if node.id in Math.default_locals:
                return Math.default_locals[node.id]
            elif node.id in locals_:
                return locals_[node.id]
            elif node.id in Math.functions:
                return Math.functions[node.id]
            else:
                _raise_from_eval(UnboundLocalError(f'Unknown variable: {node.id!r}'))
        elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
            opargs = (
                Math.eval_(node.left, locals_, ctx),
                Math.eval_(node.right, locals_, ctx)
            )
            safe, info = Math.check_safe(node, opargs)
            if safe:
                try:
                    return Math.operators[type(node.op)](*opargs)
                except ArithmeticError as e:
                    _raise_from_eval(e)
            else:
                _raise_from_eval(UnsafeError(info))
        elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            return Math.operators[type(node.op)](Math.eval_(node.operand, locals_, ctx))
        elif isinstance(node, ast.Lambda):  # lambda <args>: <body>
            return node
        elif isinstance(node, ast.Call):  # <func>(<values>)
            return Math.call(node, locals_, ctx)
        elif isinstance(node, ast.Subscript):  # <val>[<val>]
            return Math.eval_(node.value, locals_, ctx)[Math.eval_(node.slice, locals_, ctx)]
        elif isinstance(node, ast.NamedExpr):

            if isinstance(node.target, ast.Name):
                name = node.target.id
            else:
                _raise_from_eval(RuntimeError(':= target is not a Name. This is currently not supported.'))

            val = Math.eval_(node.value, locals_, ctx)
            locals_[name] = val
            return val
        elif isinstance(node, ast.JoinedStr):  # f''
            new_str = ''
            for i in node.values:
                if isinstance(i, ast.Constant):
                    new_str += i.value
                elif isinstance(i, ast.FormattedValue):
                    new_str += Math.eval_(i, locals_, ctx)
            return new_str
        elif isinstance(node, ast.FormattedValue):
            value = Math.eval_(node.value, locals_, ctx)
            fspec = Math.eval_(node.format_spec, locals_, ctx) if node.format_spec else ''

            return format(value, fspec)
        else:
            _raise_from_eval(NotImplementedError(f'Interpreting node type: {type(node)!r} is not implemented'))

    @staticmethod
    def call(node, locals_, ctx):
        if isinstance(node.func, ast.Name):
            return Math.call_function_by_name(node, locals_, ctx)
        elif isinstance(node.func, ast.Lambda):
            return Math.call_lambda(node, locals_, ctx)
        else:
            _raise_from_eval(KeyError(f'Cannot use {type(node.func)!r} as function, this interpreter might be '
                                      f'incomplete.'))

    @staticmethod
    def call_function_by_name(node: ast.Call, locals_, ctx):
        target = node.func.id
        target_func = None
        if target in Math.functions:
            target_func = Math.functions[target]
        elif target in locals_:
            target_func = locals_[target]
        else:
            _raise_from_eval(NameError(f'Unknown function {target!r}'))

        if target_func:
            kwargs = {
                keyword.arg: Math.eval_(keyword.value, locals_, ctx)
                for keyword in node.keywords
            }
            args = [Math.eval_(i, locals_, ctx) for i in node.args]
            try:
                if isinstance(target_func, FunctionWithCtx):
                    return target_func(
                        *args,
                        ctx=ctx,
                        **kwargs
                    )
                elif isinstance(target_func, ast.Lambda):
                    call = ast.Call()
                    call.func = target_func

                    call.keywords = {}
                    for k, v in kwargs.items():
                        call.keywords[k] = ast.Constant(v)

                    call.args = []
                    for i in args:
                        call.args.append(ast.Constant(i))
                    return Math.call_lambda(call, locals_, ctx)
                else:
                    return target_func(
                        *args,
                        **kwargs
                    )
            except Exception as exc:
                _raise_from_eval(exc)  # re-raise exception from inside the "sandbox".
        else:
            _raise_from_eval(KeyError(f'Unknown or unsafe function: {target!r}'))

    @staticmethod
    def call_lambda(node: ast.Call, locals_, ctx):
        func = node.func
        args = {}
        for elem in node.keywords:
            args[elem.arg] = Math.eval_(elem.value, locals_, ctx)

        for i, elem in enumerate(node.args):
            if i >= len(func.args.args):
                _raise_from_eval(TypeError(f'<lambda>() takes {len(func.args.args)} positional arguments but '
                                           f'{len(node.args) + len(args)} were given'))
            func_arg = func.args.args[i]
            if func_arg.arg in args:
                _raise_from_eval(TypeError(f'<lambda>() got multiple values for argument {func_arg.arg!r}'))
            args[func_arg.arg] = Math.eval_(elem, locals_, ctx)

        old_arg_values = {}
        for k, v in locals_.items():
            if k in args:
                old_arg_values[k] = v
        locals_.update(args)
        ret_val = Math.eval_(node.func.body, locals_=locals_, ctx=ctx)
        locals_.update(old_arg_values)
        return ret_val


class Plugin(util_bot.Plugin):
    def _latex_enabled_setting_on_load(self, channel_settings: plugin_manager.ChannelSettings):
        is_enabled = channel_settings.get(self.latex_enabled_setting)
        username = channel_settings.channel.last_known_username
        if is_enabled and username not in self._latex_channels:
            self._latex_channels.append(username)
        elif not is_enabled and username in self._latex_channels:
            self._latex_channels.remove(username)

    @property
    def latex_light_mode(self):
        return plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].get(
            self.latex_prefers_light_mode_setting)

    def __init__(self, module, source):
        super().__init__(module, source)
        self.math_help = (f'Usage: math <python code>, this command allows for usage of a restricted subset of '
                          f'Python {sys.version_info[0]}.{sys.version_info[1]}')
        self.command_math = util_bot.bot.add_command(
            'math',
            cooldown=util_bot.CommandCooldown(5, 0, 0, True)
        )(self.command_math)

        self._latex_channels = []
        self.command_render_latex = util_bot.bot.add_command(
            'latex',
            cooldown=util_bot.CommandCooldown(5, 0, 0, True)
        )(self.command_render_latex)

        self.command_latex_light_mode = util_bot.bot.add_command(
            'latexlight',
            cooldown=util_bot.CommandCooldown(5, 0, 0, True)
        )(self.command_latex_light_mode)
        self.command_render_latex.limit_to_channels = self._latex_channels

        plugin_help.create_topic('math', self.math_help,
                                 section=plugin_help.SECTION_COMMANDS,
                                 links=[
                                     'plot',
                                     'dankeval'
                                 ])

        plugin_help.create_topic(
            'latex', 'Usage: latex <latex source>. This command renders LaTeX source to a png.',
            section=plugin_help.SECTION_COMMANDS
        )

        self.latex_enabled_setting = plugin_manager.Setting(
            self,
            'math.latex_enabled',
            default_value=False,
            scope=plugin_manager.SettingScope.PER_CHANNEL,
            write_defaults=True,
            help_='Enabled LaTeX support for this channel',
            on_load=self._latex_enabled_setting_on_load
        )
        self.latex_prefers_light_mode_setting = plugin_manager.Setting(
            self,
            'math.prefers_light_mode',
            default_value=[],
            scope=plugin_manager.SettingScope.GLOBAL,
            help_='List of users who prefer light mode for their LaTeX renders.'
        )

    async def upload_image(self, image):
        headers = {
            'User-Agent': util_bot.USER_AGENT
        }
        with aiohttp.MultipartWriter() as mpwriter:
            part = mpwriter.append(image)
            part.headers['Content-Disposition'] = f'form-data; name="attachment"; filename="plot.png"'
            part.headers['Content-Type'] = f'image/png'

        headers['Content-Type'] = f'multipart/form-data; boundary={mpwriter.boundary}'

        async with aiohttp.request(
                'post',
                (
                        'https://i.nuuls.com/upload' if not util_bot.debug
                        else 'http://localhost:7494/upload'
                ),
                params={
                    'password': 'ayylmao'
                },
                data=mpwriter,
                headers=headers
        ) as r:
            text = await r.text()
            return text

    async def do_math(self, msg, code):
        ctx = Context()
        ctx.source_message = msg

        source = code
        ctx.source = source

        try:
            result = await asyncio.get_event_loop().run_in_executor(None, Math.eval_expr, source, ctx)
        except Exception as e:
            if hasattr(e, 'from_eval') and e.from_eval:
                return f'@{msg.user}, {e}'
            else:
                raise

        if isinstance(result, Plot):
            text = await self.upload_image(result.image)
            return f'@{msg.user}, Taken {result.steps_taken} steps to render. {text}'
        else:
            result = result.replace('\n', ' ').replace('\r', '')
            return f'@{msg.user}, {result}'

    async def command_math(self, msg: StandardizedMessage):
        argv = msg.text.split(' ', 1)
        if len(argv) == 1:
            return self.math_help
        code = ' '.join(argv[1:])
        print(repr(code))
        return await self.do_math(msg, code)

    async def command_latex_light_mode(self, msg: StandardizedMessage):
        if msg.user.lower() in self.latex_light_mode:
            self.latex_light_mode.remove(msg.user.lower())
            plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].update()
            with util_bot.session_scope() as session:
                session.add(plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name])
            return f'@{msg.user} Your LaTeX renders will now use dark mode.'
        else:
            self.latex_light_mode.append(msg.user.lower())
            plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name].update()
            with util_bot.session_scope() as session:
                session.add(plugin_manager.channel_settings[plugin_manager.SettingScope.GLOBAL.name])
            return f'@{msg.user}, Your LaTeX renders will now use light mode.'

    async def command_render_latex(self, msg: StandardizedMessage):
        target_user = msg.flags.get('reply-parent-user-login')  # original message text (reply route)
        target_text = msg.flags.get('reply-parent-msg-body')

        if not target_text:
            # not a reply, use given text
            args = msg.text.split(' ', 1)
            if len(args) != 2:
                return (util_bot.CommandResult.OTHER_FAILED,
                        f'@{msg.user}, {args[0] if args else "_tex"} command needs LaTeX source to render, a '
                        f'message (reply to one) or @username for someone\'s last message.')
            if args[1].startswith('@'):
                target_user = args[1].split(' ', 1)[0].strip('@,').lower()
                last_messages = plugin_chat_cache.find_messages(msg.channel, target_user)
                if len(last_messages) == 0 or (target_user == msg.user and len(last_messages) < 2):
                    return (util_bot.CommandResult.OTHER_FAILED,
                            f'@{msg.user}, User has no known recent messages.')
                if target_user == msg.user:
                    # special case: don't render the command text
                    last_msg = last_messages[-2]
                else:
                    last_msg = last_messages[-1]
                target_text = last_msg.text
            else:
                target_text = args[1]
        if r'\begin{document}' in target_text:
            txt = LATEX_MINIMAL_DOC_FORMAT + target_text
        else:
            if msg.user not in self.latex_light_mode:
                target_text = f'\\darkmode{{\n{target_text}\n}}'
            txt = LATEX_DOCUMENT_FORMAT.replace('%REPLACE THIS WITH MESSAGE, PLS THX', target_text)
        proc = await asyncio.create_subprocess_shell('sudo -u nobody bash /usr/local/bin/compile_latex.sh',
                                                     stdin=subprocess.PIPE,
                                                     stdout=subprocess.PIPE)
        prefix = (await proc.stdout.readline()).decode().strip()
        proc.stdin.write((txt + '\n').encode())
        proc.stdin.close()

        # log output from pdflatex
        output = b''
        while 1:
            chunk = await proc.stdout.read(1024)
            if not chunk:
                break
            output += chunk
        output = output.decode()

        await proc.wait()
        if getattr(log, 'log', None):
            log.log('info', f'User {msg.user}({target_user=}) rendered {target_text!r}. Exit code: {proc.returncode}. '
                            f'PID was {proc.pid}',
                    cause=CAUSE_COMMAND)
            log.log('debug', f'Output for pid {proc.pid}: {output}',
                    cause=CAUSE_COMMAND)
        if proc.returncode != 0:
            count_errors = output.count('! ')
            small_err_start = output.find('! ')
            small_err_end = output.find('! Emergency stop.')
            err = output[small_err_start:small_err_end].replace('\n', ' ').strip()
            while '  ' in err:
                err = err.replace('  ', ' ')
            message_begin = f'@{msg.user}, Error while rendering (exit code {proc.returncode}): '
            if len(err) + len(message_begin) > 500:
                return (f'{message_begin}error is too big here is a link: '
                        f'{plugin_hastebin.hastebin_addr}{await plugin_hastebin.upload(output)}')
            if count_errors > 1:
                return (
                    f'{message_begin}{err} '
                    f'{plugin_hastebin.hastebin_addr}{await plugin_hastebin.upload(output)}'
                )
            return f'{message_begin}{err}'

        with open(os.path.join(prefix, 'output.png'), 'rb') as f:
            data = f.read()
        await (await asyncio.create_subprocess_shell(f'sudo -u nobody /bin/rm -rf {shlex.quote(prefix)}')).wait()

        try:
            text = await self.upload_image(data)
        except FileNotFoundError:
            return f'@{msg.user}, Error while rendering, sorry no leaking things.'

        if target_user:
            return f'@{msg.user}, @{target_user}, {text}'
        else:
            return f'@{msg.user}, {text}'

    @property
    def no_reload(self):
        return False

    @property
    def name(self) -> str:
        return NAME

    def on_reload(self):
        return None


LATEX_MINIMAL_DOC_FORMAT = r'''\documentclass[preview]{standalone}
%\usepackage[utf8x]{inputenc}
\usepackage{ucs}
\usepackage{fontspec}
\usepackage[version=4]{mhchem}
\usepackage{xcolor}
\usepackage{wasysym}

\newcommand{\darkmode}[1]{
    \colorbox{black}{
        \textcolor{white} {
           #1
        }
    }
}

'''

LATEX_DOCUMENT_FORMAT = LATEX_MINIMAL_DOC_FORMAT + r'''\begin{document}
    %REPLACE THIS WITH MESSAGE, PLS THX
\end{document}
'''
