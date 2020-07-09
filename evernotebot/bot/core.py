import copy
import json
import importlib
import math

from utelegram import TelegramBot, TelegramBotError
from utelegram import Message

import evernotebot.util.evernote.client as evernote_api
from evernotebot.bot.commands import (
    start_command, switch_mode_command, switch_notebook_command, help_command
)
from evernotebot.bot.models import BotUser
from evernotebot.bot.shortcuts import (
    get_evernote_oauth_data, get_cached_object, download_telegram_file
)
from evernotebot.util.evernote.client import EvernoteApi


class EvernoteBotException(TelegramBotError):
    pass


class EvernoteBot(TelegramBot):
    def __init__(self, config):
        telegram_config = config['telegram']
        token = telegram_config['token']
        bot_url = 'https://t.me/{}'.format(telegram_config['bot_name'])
        super().__init__(token, bot_url=bot_url, config=config)
        self._evernote_apis_cache = {}
        storage_config = config['storage']
        self.users = self._init_storage(storage_config['users'])
        self.failed_updates = self._init_storage(storage_config['failed_updates'])
        self.register_handlers()

    def _init_storage(self, config: dict):
        module_name, classname = config["class"].rsplit(".", 1)
        module = importlib.import_module(module_name)
        config_copy = copy.deepcopy(config)
        del config_copy["class"]
        StorageClass = getattr(module, classname)
        return StorageClass(**config_copy)

    def stop(self):
        self.users.close()
        self.failed_updates.close()

    def evernote(self, bot_user: BotUser=None) -> EvernoteApi:
        if bot_user is None:
            return get_cached_object(self._evernote_apis_cache, None,
                                     constructor=lambda: evernote_api)
        access_token = bot_user.evernote.access.token
        sandbox = self.config.get("debug", True)
        return get_cached_object(self._evernote_apis_cache, bot_user.id,
            constructor=lambda: EvernoteApi(access_token, sandbox))

    def register_handlers(self):
        self.set_update_handler("message", self.on_message)
        self.set_update_handler("edited_message", self.on_message)
        commands = {
            "start": start_command,
            "switch_mode": switch_mode_command,
            "notebook": switch_notebook_command,
            "help": help_command,
        }
        for name, handler in commands.items():
            self.set_command_handler(name, handler)

    def on_message(self, bot, message: Message):
        user_id = message.from_user.id
        user_data = self.users.get(user_id)
        if not user_data:
            raise EvernoteBotException(f"Unregistered user {user_id}. "
                                        "You've to send /start command to register")
        bot_user = BotUser(**user_data)
        if not bot_user.evernote or not bot_user.evernote.access.token:
            raise EvernoteBotException("You have to sign in to Evernote first. "
                                       "Send /start and press the button")
        if bot_user.state:
            self.handle_state(bot_user, message)
        else:
            self.handle_message(message)

    def handle_state(self, bot_user: BotUser, message: Message):
        state = bot_user.state
        handlers_map = {
            'switch_mode': self.switch_mode,  # self.switch_mode()
            'switch_notebook': self.switch_notebook,  # self.switch_notebook()
        }
        state_handler = handlers_map[state]
        state_handler(bot_user, message.text)
        bot_user.state = None
        self.users.save(bot_user.asdict())

    def handle_message(self, message: Message):
        message_attrs = ('text', 'photo', 'voice', 'audio', 'video', 'document', 'location')
        for attr_name in message_attrs:
            value = getattr(message, attr_name, None)
            if value is None:
                continue
            status_message = self.api.sendMessage(message.chat.id, f'{attr_name.capitalize()} accepted')
            handler = getattr(self, f'on_{attr_name}')
            handler(message)
            self.api.editMessageText(message.chat.id, status_message['message_id'], 'Saved')

    def get_caption(self, message: Message):
        if message.forward_from:
            user = message.forward_from
            parts = filter(lambda x: x, (user.first_name, user.last_name))
            name = ' '.join(parts)
            if user.username:
                name += f' {user.username}'
            return f'Forwarded from {name}'
        if message.forward_from_chat:
            chat = message.forward_from_chat
            name = chat.title or chat.username
            return f'Forwarded from {chat.type} {name}'
        if message.forward_sender_name:
            return f'Forwarded from {message.forward_sender_name}'
        return message.caption


    def _validate_mode(self, selected_mode_str):
        mode = selected_mode_str
        if selected_mode_str.startswith('> ') and selected_mode_str.endswith(' <'):
            mode = selected_mode_str[2:-2]
        title = mode
        mode = mode.lower().replace(' ', '_')
        if mode not in {'one_note', 'multiple_notes'}:
            raise EvernoteBotException(f"Unknown mode '{title}'")
        return mode, title

    def switch_mode(self, bot_user: BotUser, selected_mode_str: str):
        new_mode, new_mode_title = self._validate_mode(selected_mode_str)
        chat_id = bot_user.telegram.chat_id
        if bot_user.bot_mode == new_mode:
            text = f"The bot already in '{new_mode_title}' mode."
            self.api.sendMessage(chat_id, text, json.dumps({"hide_keyboard": True}))
            return
        if new_mode == "one_note":
            self.switch_mode_one_note(bot_user)
            return
        # switching to 'multiple_notes' mode
        bot_user.evernote.shared_note_id = None
        bot_user.bot_mode = new_mode
        text = f"The bot has switched to '{new_mode_title}' mode."
        self.api.sendMessage(chat_id, text, json.dumps({"hide_keyboard": True}))

    def switch_notebook(self, bot_user: BotUser, notebook_name: str):
        if notebook_name.startswith("> ") and notebook_name.endswith(" <"):
            notebook_name = notebook_name[2:-2]
        query = {"name": notebook_name}
        notebooks = self.evernote(bot_user).get_all_notebooks(query)
        if not notebooks:
            raise EvernoteBotException(f"Notebook '{notebook_name}' not found")
        # TODO: self.create_note(notebook) if bot_user.bot_mode == 'one_note'
        notebook = notebooks[0]
        bot_user.evernote.notebook.name = notebook["name"]
        bot_user.evernote.notebook.guid = notebook["guid"]
        chat_id = bot_user.telegram.chat_id
        self.api.sendMessage(chat_id, f"Current notebook: {notebook['name']}",
                             json.dumps({"hide_keyboard": True}))

    def switch_mode_one_note(self, bot_user: BotUser):
        chat_id = bot_user.telegram.chat_id
        evernote_data = bot_user.evernote
        if evernote_data.access.permission == 'full':
            note = self.evernote(bot_user).create_note(
                evernote_data.notebook.guid,
                title='Telegram bot notes'
            )
            bot_user.bot_mode = 'one_note' # TODO: move up
            evernote_data.shared_note_id = note.guid
            note_url = self.evernote(bot_user).get_note_link(note.guid)
            text = f'Your notes will be saved to <a href="{note_url}">this note</a>'
            self.api.sendMessage(chat_id, text, json.dumps({'hide_keyboard': True}), parse_mode='Html')
        else:
            text = 'To enable "One note" mode you have to allow to the bot both reading and updating your notes'
            self.api.sendMessage(chat_id, text, json.dumps({'hide_keyboard': True}))
            message_text = 'Please, sign in and give the permissions to the bot.'
            bot_user.evernote.oauth = get_evernote_oauth_data(self, bot_user,
                message_text, access='full')

    def save_note(self, user: BotUser, text=None, title=None, **kwargs):
        if user.bot_mode == 'one_note':
            note_id = user.evernote.shared_note_id
            self.evernote(user).update_note(note_id, text, title, **kwargs)
        else:
            notebook_id = user.evernote.notebook.guid
            self.evernote(user).create_note(notebook_id, text, title, **kwargs)

    def _check_evernote_quota(self, bot_user: BotUser, file_size):
        quota = self.evernote(bot_user).get_quota_info()
        if quota["remaining"] < file_size:
            reset_date = quota["reset_date"].strftime("%Y-%m-%d %H:%M:%S")
            remain_bytes = quota['remaining']
            raise EvernoteBotException(f"Your evernote quota is out ({remain_bytes} bytes remains till {reset_date})")

    def _save_file_to_evernote(self, file_id, file_size, message: Message):
        max_size = 20 * 1024 * 1024 # telegram restriction. We can't download any file that has size more than 20Mb
        if file_size > max_size:
            raise EvernoteBotException('File too big. Telegram does not allow to the bot to download files over 20Mb.')
        filename, short_name = download_telegram_file(self.api, file_id, self.config["tmp_root"])
        user_data = self.users.get(message.from_user.id)
        user = BotUser(**user_data)
        self._check_evernote_quota(user, file_size)
        title = self.get_caption(message) or (message.text and message.text[:20]) or 'File'
        files = ({'path': filename, 'name': short_name},)
        text = ''
        telegram_link = message.get_telegram_link()
        if telegram_link:
            text = f'<div><p><a href="{telegram_link}">{telegram_link}</a></p><pre>{message.caption}</pre></div>'
        self.save_note(user, '', title=title, files=files, html=text)

    def on_text(self, message: Message):
        def format_html(message: Message):
            if not message.entities:
                return message.get_text()
            pointer = 0
            strings = []
            for entity in message.entities:
                strings.append(message.get_text(pointer, entity.offset))
                start, end = entity.offset, entity.offset + entity.length
                if start < pointer:
                    continue
                string = message.get_text(start, end)
                if entity.type == 'text_link':
                    url = entity.url
                    html = f'<a href="{url}">{string}</a>'
                elif entity.type == 'pre':
                    html = f'<pre>{string}</pre>'
                elif entity.type == 'bold':
                    html = f'<b>{string}</b>'
                elif entity.type == 'italic':
                    html = f'<i>{string}</i>'
                elif entity.type == 'underline':
                    html = f'<u>{string}</u>'
                elif entity.type == 'strikethrough':
                    html = f'<s>{string}</s>'
                else:
                    html = string
                strings.append(html)
                pointer = end
            strings.append(message.get_text(pointer))
            text = ''.join(strings)
            text = '<br />'.join(text.split('\n'))
            return text

        user_data = self.users.get(message.from_user.id)
        user = BotUser(**user_data)
        html = format_html(message)
        telegram_link = message.get_telegram_link()
        if telegram_link:
            html = f'<div><p><a href="{telegram_link}">{telegram_link}</a></p>{html}</div>'
        title = self.get_caption(message) or '[Telegram bot]'
        self.save_note(user, '', title=title, html=html)

    def on_photo(self, message: Message):
        max_size = 20 * 1024 * 1024 # telegram restriction. We can't download any file that has size more than 20Mb
        file_id = None
        file_size = math.inf
        for photo in message.photo: # pick the biggest file
            if photo.file_size <= max_size and \
                (file_size == math.inf or file_size < photo.file_size):
                file_size = photo.file_size
                file_id = photo.file_id
        self._save_file_to_evernote(file_id, file_size, message)

    def on_voice(self, message: Message):
        file_id = message.voice.file_id
        file_size = message.voice.file_size
        self._save_file_to_evernote(file_id, file_size, message)

    def on_document(self, message: Message):
        file_size = message.document.file_size
        file_id = message.document.file_id
        self._save_file_to_evernote(file_id, file_size, message)

    def on_video(self, message: Message):
        file_size = message.video.file_size
        file_id = message.video.file_id
        self._save_file_to_evernote(file_id, file_size, message)

    def on_location(self, message: Message):
        latitude = message.location.latitude
        longitude = message.location.longitude
        maps_url = f'https://maps.google.com/maps?q={latitude},{longitude}'
        title = 'Location'
        html = f'<a href="{maps_url}">{maps_url}</a>'
        if message.venue:
            venue = message.venue
            title=venue.title or title
            address=venue.address
            html = f'{title}<br />{address}<br /><a href="{maps_url}">{maps_url}</a>'
            foursquare_id = venue.foursquare_id
            if foursquare_id:
                url = f'https://foursquare.com/v/{foursquare_id}'
                html += f'<br /><a href="{url}">{url}</a>'
        user_data = self.users.get(message.from_user.id)
        user = BotUser(**user_data)
        title = self.get_caption(message) or title
        self.save_note(user, title=title, html=html)
