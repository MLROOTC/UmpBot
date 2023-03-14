from dhooks import Webhook
import configparser
import src.Ump.gameplay_loop as loop
import sys
import time
import traceback

config = configparser.ConfigParser()
config.read('config.ini')
debug_hook = Webhook(config['Channels']['error_log_webhook'])

debug_hook.send(f'audit_game_logs.py started with python {sys.version}')
while True:
    try:
        print('loop')
        loop.audit_all_games()
        print('done')
    except Exception as e:
        print(e)
        print(traceback.format_exc())
    time.sleep(30 * 60)
debug_hook.send('audit_game_logs.py stopped...')
