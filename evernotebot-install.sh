#!/bin/sh

read_env_variable() {
	read -rp "$1=" value
	echo "export $1=\"$value\"" >> "$env_file"
}

create_env() {
	# $1 - install_dir, $2 - env_file
	echo "export EVERNOTEBOT_DIR=\"$install_dir\"" >> "$env_file"
	read_env_variable "EVERNOTEBOT_DEBUG"
	read_env_variable "EVERNOTEBOT_HOSTNAME"
	read_env_variable "EVERNOTEBOT_EXPOSE_PORT"

	read_env_variable "TELEGRAM_BOT_NAME"
	read_env_variable "TELEGRAM_API_TOKEN"

	read_env_variable "EVERNOTE_READONLY_KEY"
	read_env_variable "EVERNOTE_READONLY_SECRET"

	read_env_variable "EVERNOTE_READWRITE_KEY"
	read_env_variable "EVERNOTE_READWRITE_SECRET"

	source "$env_file"
	echo "source $env_file" >> ~/.bashrc
	echo "A line \"source $env_file\" added to your .bashrc"
}

# Check current user in docker group
OS="$(uname -s)"
if [ "$OS" = "Linux" ]; then
	groups | grep docker > /dev/null
	status=$?
	if [ $status -ne 0 ]; then
		echo "User $USER must be in group docker"
		exit 1
	fi
else
	if [ "$OS" = "Darwin" ]; then
		groups | grep staff > /dev/null
		status=$?
		if [ $status -ne 0 ]; then
			echo "User $USER must be in group staff"
			exit 1
		fi
	fi
fi

# Set up installation directory
current_dir=$(pwd)
read -rp "Install directory (default: $current_dir): " install_dir
if [ ! "$install_dir" ]; then
	install_dir="$current_dir"
else
	mkdir -p "$install_dir"
fi
cd "$install_dir"
echo "Installation directory: $install_dir"
export EVERNOTEBOT_DIR="$install_dir"

docker pull djudman/evernote-telegram-bot

# Create docker volume for bot data
VOLUME_NAME="evernotebot-data"

docker volume inspect $VOLUME_NAME > /dev/null 2>&1
status=$?
if [ $status -ne 0 ]; then
	echo "Volume $VOLUME_NAME created."
	docker volume create $VOLUME_NAME > /dev/null 2>&1
else
	echo "Volume $VOLUME_NAME already exists"
fi

# Get an script for start/stop/update from github
curl https://raw.githubusercontent.com/djudman/evernote-telegram-bot/master/init.d/evernotebot --output ./evernotebot
chmod u+x ./evernotebot

# Build `.env` file in installation directory. This file will contain environment variables
env_file="$install_dir/.env"
if [ -f "$env_file" ]; then
	read -rp "Env file $env_file already exists. Do you want to rewrite it? (Y/n) " delete
	if [ ! "$delete" ] || [ "$delete" = "Y" ]; then
		old_env_file="$env_file.bak"
		mv "$env_file" "$old_env_file"
		touch "$env_file"
		create_env
	fi
else
	create_env
fi

echo "Evernote bot successfuly installed to $install_dir"
echo "Use ./evernotebot start|stop|restart|update"