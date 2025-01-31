# BlueSky To Telegram Repost Bot

## Dependencies

Requires Python 3.11.x & a Selenium Chrome Webdriver for local development (Should work with other Chromium Browsers, such as Brave, as well).

## Environment variables

### SCREENSHOT_DIRECTORY

Mandatory if run outside of Docker.

Directory for temporary screenshots. Directory will not be cleared by this bot.

### SQLALCHEMY_URL

Mandatory if run outside of Docker.  

The SQLAlchemy connection string. Note: Currently, only async SQLite has been verified to work.

### SQLITE_DB_FILENAME

Mandatory if run with Docker.

A filename for an SQLite database. This database keeps track of user subscriptions.

### LOCAL_DEVELOPMENT_CHROME_BINARY

Mandatory if run outside of Docker.  

Specifies the path to the Chrome binary.

### SQLITE_DB_DIR_HOST_PATH

Mandatory if run with Docker.

Specifies the host directory for `SQLITE_DB_FILENAME`.

### OBSERVER_USER, OBSERVER_PASSWORD

Mandatory.

Specifies the login credentials for observing content. This account should stay entirely hidden from anyone's eyes so 
it practically cannot be blocked by users you'd like to observe.

### OBSERVER_USER_ALTERNATIVE, OBSERVER_PASSWORD_ALTERNATIVE

Optional.

As above, but is used as a fallback to evade rate limits. 

## TELEGRAM_API_KEY

Mandatory.

Your Bot's Telegram API key.

## Run (Docker)

Run 

```console
OBSERVER_LOGIN=your-bluesky-obser@login.me \
  OBSERVER_PASSWORD=some-password \
  OBSERVER_LOGIN_ALTERNATIVE=your-other-bluesky-obser@login.me \
  OBSERVER_PASSWORD_ALTERNATIVE=some-other-password \
  TELEGRAM_API_KEY=telgreamapikey \
  SQLITE_DB_DIR_HOST_PATH=/Some/where/where/sqlite/file/should/be \
  SQLITE_DB_FILENAME=db.sqlite \
  docker compose build &&
  OBSERVER_LOGIN=your-bluesky-obser@login.me \
  OBSERVER_PASSWORD=some-password \
  OBSERVER_LOGIN_ALTERNATIVE=your-other-bluesky-obser@login.me \
  OBSERVER_PASSWORD_ALTERNATIVE=some-other-password \
  TELEGRAM_API_KEY=telgreamapikey \
  SQLITE_DB_DIR_HOST_PATH=/Some/where/where/sqlite/file/should/be \
  SQLITE_DB_FILENAME=db.sqlite \
  docker compose up -d
```

See above for details about the environment variables.

## Run (Local)

```console
> cd bot
> pip install -r requirements.txt && python main.py -m manage_subscriptions
```

```console
> cd bot
> pip install -r requirements.txt && python main.py -m distribute_content
```

Make sure that all environment variables are specified. 

You can use a .env file to do so.

## Note

I've been observing stability issues all over the place - Python's asyncio unfortunately seems a little unstable within this context,
Selenium sometimes causes issues with it's session handling and unfortunately drops sessions.

In order to mitigate these issues, you could use a cron job (for now) to let Docker restart the container every 10 minutes or so.
You'll might miss some content this way, but this is still preferable to running into some weird, invalid state.