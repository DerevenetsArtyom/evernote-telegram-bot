Telegram bot for Evernote
=========================

This bot can save everything that you send to your Evernote account.

You can use this bot in Telegram: https://t.me/evernoterobot  
*Or* you can use *your own* telegram bot and your own server, then see [Installation](#Installation)

# Installation
If you have some reasons do not use my bot deployed on my server, you can use
your own installation.  

* Create your own bot with the
[BotFather](https://telegram.me/BotFather)
(see https://core.telegram.org/bots#3-how-do-i-create-a-bot)
* Create your own Evernote application and obtain a pair of keys (access key and access secret) 
    * Go to https://dev.evernote.com/doc/ and press the green button *"GET AN API KEY"*
* Install a Docker to your server (see https://docs.docker.com/install/)
* Get and set up SSL certificate (see https://letsencrypt.org)
* Set up [nginx](https://nginx.org)/[caddy](https://caddyserver.com)/another proxy server to work with your SSL certificate.
* Check you have *[curl](https://curl.haxx.se/download.html)* on your server (usually it's installed by default)
* Execute this command: `sudo curl https://raw.githubusercontent.com/djudman/evernote-telegram-bot/master/evernotebot-install.sh --output evernotebot-install.sh && sh evernotebot-install.sh`
    * `sudo` is needed because there is copying a file to `/etc/init.d` directory
    * you will need to enter some data as:
        * telegram api token
        * evernote access key
        * evernote access secret
        * etc., see [Environment variables](#Environment-variables)
* Execute `/etc/init.d/evernotebot start` to start bot

## How to build docker image manually

* Clone source code to your server
    ```
    git clone https://github.com/djudman/evernote-telegram-bot.git
    ```
* Build image
    ```
    docker build -t evernote-telegram-bot .
    ```
* Define [environment variables](#Environment-variables) (for example, in `.bashrc`)
* Create a docker volume to store data
    `docker volume create evernotebot-data`
* Run a container
    ```
    docker run \
        -e EVERNOTEBOT_DEBUG="$EVERNOTEBOT_DEBUG" \
        -e MONGO_HOST="$MONGO_HOST" \
        -e EVERNOTEBOT_HOSTNAME="$EVERNOTEBOT_HOSTNAME" \
        -e TELEGRAM_API_TOKEN="$TELEGRAM_API_TOKEN" \
        -e TELEGRAM_BOT_NAME="$TELEGRAM_BOT_NAME" \
        -e EVERNOTE_BASIC_ACCESS_KEY="$EVERNOTE_BASIC_ACCESS_KEY" \
        -e EVERNOTE_BASIC_ACCESS_SECRET="$EVERNOTE_BASIC_ACCESS_SECRET" \
        -e EVERNOTE_FULL_ACCESS_KEY="$EVERNOTE_FULL_ACCESS_KEY" \
        -e EVERNOTE_FULL_ACCESS_SECRET="$EVERNOTE_FULL_ACCESS_SECRET" \
        -d \
        -p 127.0.0.1:8000:8000 \
        --restart=always \
        --name=evernotebot \
        -it \
        -v ./logs:/app/logs:rw \
        --mount source="evernotebot-data",target="/evernotebot-data" \
        evernote-telegram-bot
    ```

# Environment variables
| Variable name                | Default value | Description |
|------------------------------|---------------|-------------|
| EVERNOTEBOT_DEBUG            | 0             | Enable debug mode (additional logging enabled) |
| EVERNOTEBOT_HOSTNAME         | evernotebot.djud.me | DNS name of your host
| TELEGRAM_API_TOKEN           | -             | Access token for telegram API. You can obtain this by BotFather |
| TELEGRAM_BOT_NAME            | evernoterobot | Name of telegram bot. You used this in BotFather |
| EVERNOTE_BASIC_ACCESS_KEY    | -             | appKey for your Evernote app (with readonly permissions) |
| EVERNOTE_BASIC_ACCESS_SECRET | -             | secret for your Evernote app (with readonly permissions) |
| EVERNOTE_FULL_ACCESS_KEY     | -             | appKey for your Evernote app (with read/write permissions) |
| EVERNOTE_FULL_ACCESS_SECRET  | -             | secret for your Evernote app (with read/write permissions) |
| MONGO_HOST                   | 127.0.0.1     | Hostname for mongodb host|

# 🚢 Deploy with Dokku (DO-based)

Assuming you have set up everything on Digital Ocean:

### On Dokku machine:
1. Create an application (in Dokku terms).  
   Make sure you've picked up an appropriate name to have it as a subdomain.
```
dokku apps:create tg-evernote
```

2. Make sure Dokku knows about your main domain and add subdomain for the app.
```
dokku domains:set-global [your.main.domain]
dokku domains:set tg-evernote tg-evernote.[your.main.domain]
```

3. Set up config variables to be able to run the bot.  
   In case you're migrating from Heroku - run `heroku config` and adjust an output.

```
dokku config:set tg-evernote EVERNOTEBOT_DEBUG=0
dokku config:set tg-evernote EVERNOTEBOT_HOSTNAME=""
dokku config:set tg-evernote EVERNOTE_OAUTH_CALLBACK=""
dokku config:set tg-evernote TELEGRAM_API_TOKEN=""
dokku config:set tg-evernote TELEGRAM_BOT_NAME=""
dokku config:set tg-evernote EVERNOTE_BASIC_ACCESS_KEY=""
dokku config:set tg-evernote EVERNOTE_BASIC_ACCESS_SECRET=""
dokku config:set tg-evernote EVERNOTE_FULL_ACCESS_KEY=""
dokku config:set tg-evernote EVERNOTE_FULL_ACCESS_SECRET=""
```

4. Setup LetsEncrypt certs and Postgres database - install Postgres plugin and link DB with the app.
```
# Enable LetsEncrypt for the application
dokku letsencrypt:enable tg-evernote

# Check that everything is correct
dokku letsencrypt:list
dokku certs:report tg-evernote

# DB Setup
sudo dokku plugin:install https://github.com/dokku/dokku-postgres.git

dokku postgres:create evernotebot
dokku postgres:link evernotebot tg-evernote
```

### On your local machine

The only thing you need to do - add another remote to be able to push the code there.

```
git remote add dokku dokku@[your.server.ip.address]:[app_name]
```
Then you should be able to deploy your app just by typing
```
git push dokku master:master
```
