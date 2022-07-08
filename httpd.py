import os
from dotenv import load_dotenv
from wsgiref.simple_server import make_server

from evernotebot.app import EvernoteBotApplication

load_dotenv()  # take environment variables from .env.

host = '0.0.0.0'
port = int(os.getenv("PORT", "5000"))
app = EvernoteBotApplication()

try:
    with make_server(host, port, app) as httpd:
        print(f'Starting `evernotebot` at http://{host}:{port}...')
        httpd.serve_forever()
except KeyboardInterrupt:
    app.shutdown()
