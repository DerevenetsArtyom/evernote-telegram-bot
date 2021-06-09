import json
import logging.config
import os
import re
from os.path import dirname, join, realpath, exists
from logging import Formatter


def load_config():
    filename = join(dirname(dirname(__file__)), 'evernotebot.config.json')
    dirpath = realpath(dirname(filename))
    with open(filename, 'r') as f:
        config_str_data = f.read()
    matches = re.findall(r'\$\{([0-9a-zA-Z_]+)\}', config_str_data)
    defaults = {
        'MONGO_HOST': '127.0.0.1',
        'EVERNOTEBOT_DEBUG': False,
        'EVERNOTEBOT_HOSTNAME': 'evernotebot.djud.me',
        'TELEGRAM_BOT_NAME': 'evernoterobot',
    }
    for name in matches:
        value = os.getenv(name, defaults.get(name))
        if value is None:
            raise Exception(f"Environment variable `{name}` isn't set")
        value = value or ''
        config_str_data = config_str_data.replace(f'${{{name}}}', value)
    config = json.loads(config_str_data)
    if config['debug'].isdigit():
        config['debug'] = int(config['debug'])
    config['debug'] = bool(config['debug'])
    if config['debug']:
        loggers = config['logging']['loggers'].keys()
        for logger_name in loggers:
            config['logging']['loggers'][logger_name]['handlers'].append('stdout')
    filepath = join(dirpath, config['logging']['handlers']['evernotebot']['filename'])
    logdir = dirname(filepath)
    if not exists(logdir):
        os.makedirs(logdir, exist_ok=True)
    logging.config.dictConfig(config['logging'])
    return config


class JsonFormatter(Formatter):
    def format(self, record):
        return json.dumps({
            'logger': record.name,
            'file': '{0}:{1}'.format(record.pathname, record.lineno),
            'data': record.msg,
        })
