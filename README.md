# BlueSky Repost Bot

## Dependencies

Requires Python 3.11.x & a Selenium Chrome Webdriver for local development (Should work with other Chromium Browsers, such as Brave, as well).

## Environment variables

### ACCOUNTS_JSON

Mandatory.

Create a json file and add accounts with their [DID](https://atproto.com/specs/did) to it. This represents the list of 
accounts the Bot should observe.

Example:

```json
{
    "someone.bsky.social": "did:plc:2w03yyl2dwg4cu3ksgypx6a2",
    "someoneelse.bsky.social": "did:plc:pb94x4ncbsgvkh53s6dqgyol"
}
```

Make sure to follow the pattern shown above. The path to that file should then be specified in the `ACCOUNTS_JSON`
environment variable. You can update the file's content at any given point in time, but make sure it stays valid.

You can find the DID of any account using

[https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle=theaccount.bsky.social](https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle=m1kola.bsky.social)

Docker will mount that path.

### SCREENSHOT_DIRECTORY

Mandatory.

Specifies the path to the directory where screenshots should be stored. Docker will mount that path into the container.

### PUBLISHER_USER, PUBLISHER_PASSWORD

Optional.

Specifies the login credentials for the account that should repost the observed content. Posts will contain screenshots 
of the source material.

*Note*: Since users could still block your publisher account and thus prevent it from reading their content, you should 
use different credentials for observing and posting content.

Both environment variables are optional. The bot will only store screenshots of observed content if any of the two
environment variables is not set.

### OBSERVER_USER, OBSERVER_PASSWORD

Mandatory.

Specifies the login credentials for observing content. This account should stay entirely hidden from anyone's eyes so 
it practically cannot be blocked by users you'd like to observe.

### LOCAL_DEVELOPMENT_CHROME_BINARY

Mandatory if run outside of Docker.  

Specifies the path to the Chrome binary.

## TELEGRAM_API_KEY

Optional.

Your Telegram API key.

## TELEGRAM_CHANNEL_ID

Optional.

Channel ID for republish content on Telegram.

## Run (Docker)

Run 

```console
PUBLISHER_LOGIN=your-publisher-account@someprovider.me \
    PUBLISHER_PASSWORD=your-publisher-password \
    OBSERVER_LOGIN=your-observer-account@proton.me \
    OBSERVER_PASSWORD=your-observer-password \
    TELEGRAM_API_KEY=telegram-api-key \
    TELEGRAM_CHANNEL_ID=telegram-channel-id \
    SCREENSHOT_DIRECTORY=/your/path/to/store/screenshots \
    ACCOUNTS_JSON=/path/to/your/accounts.json
    docker-compose up
```

See above for details about the environment variables.

## Run (Local)

```console
> cd bot
> pip install -r requirements.txt && python main.py
```

Make sure that all environment variables are specified. 

You can use a .env file to do so.

## Note

I've been observing stability issues all over the place - Python's asyncio unfortunately seems a little unstable within this context,
Selenium sometimes causes issues with it's session handling and unfortunately drops sessions.

In order to mitigate these issues, you could use a cron job (for now) to let Docker restart the container every 30 minutes or so.
You'll might miss some content this way, but this is still preferable to running into some weird, invalid state.