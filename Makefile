test:
	python3 tests/run.py
build:
	docker build --no-cache -t djudman/evernote-telegram-bot .
	docker push djudman/evernote-telegram-bot
run:
	EVERNOTEBOT_DIR="$(HOME)/github/djudman/evernote-telegram-bot" ./init.d/evernotebot start
