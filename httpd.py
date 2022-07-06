from wsgiref.simple_server import make_server

from dotenv import load_dotenv

from evernotebot.app import EvernoteBotApplication

load_dotenv()  # take environment variables from .env.

host, port = '0.0.0.0', 8080
app = EvernoteBotApplication()

try:
    with make_server(host, port, app) as httpd:
        print(f'Starting `evernotebot` at http://{host}:{port}...')
        httpd.serve_forever()
except KeyboardInterrupt:
    app.shutdown()
