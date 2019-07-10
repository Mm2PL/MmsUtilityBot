try:
    # noinspection PyPackageRequirements
    import main
    # wtf PyCharm, why do you think `main` is an installable package
except ImportError:
    import util_bot as main


    def log(level, *msg):
        print(level, *msg)


    exit()
import twitchirc

__meta_data__ = {
    'name': 'auto_load',
    'commands': []
}
log = main.make_log_function('auto_load')

log('info', 'Plugin `auto_load` loaded')

if 'plugins' in main.bot.storage.data:
    for i in main.bot.storage['plugins']:
        log('info', f'Trying to load file: {i}')
        try:
            main.load_file(i)
        except Exception as e:
            log('warn', f'Failed to load: {e}')
else:
    main.bot.storage['plugins'] = []


@main.bot.add_command('load_plugin', required_permissions=['util.load_plugin'], enable_local_bypass=False)
def command_load_plugin(msg: twitchirc.ChannelMessage):
    argv = msg.text.split(' ')
    if len(argv) > 1:
        argv.pop(0)  # Remove the command name
    try:
        pl = main.load_file(argv[0])
        main.bot.send(msg.reply(f'Successfully loaded plugin: {pl.name}'))
    except Exception as e:
        main.bot.send(msg.reply(f'An exception was encountered: {e}'))
