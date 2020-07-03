# sendnotification

A small CLI tool and python lib for sending notifications using different
services.

Supported services

- Pushover
- Email

Supports interval setting (X seconds) to prevent sending the same notification
against a specific service multiple times within interval.
This requires `redis`.

## Send notification example using config file

```python
from sendnotification import SendNotification

send_notification = SendNotification()
send_notification.send('Notification message')
```

## Send notification from command line using config file

```shell
sendnotification [-i/--interval 3600] 'Notification message'
```

## Add interval, only send a notification every interval sec

```python
send_notification.send('Notification message', interval=3600)
```

## Manual setup without config

```python
send_notification = SendNotification(config_file=False)
send_notification.config = {
    'services': ['pushover'],
    'pushover': {
        'app_token': '...',
        'api_key': '...'
    }
}
send_notification.send('Notification message')
```

## Pushover notification

```python
send_notification.send_pushover(app_token, api_key, message, interval=None, title=None)
```

## Email notification

```python
send_notification.send_email(subject, to, message, interval=None, sender=None)
```

## Config

`~/.sendnotification`

```json
{
        "services": [
                {"title": "pushover", "settings": {"app_token": "...", "api_key": "..."}},
                {"title": "email", "settings": {"subject": "...", "to": "..."}}
        ]
}
```

## Config with optionals

`~/.sendnotification` with optionals

```json
{
        "services": [
                {"title": "pushover", "settings": {"app_token": "...", "api_key": "...", "title": "..."}},
                {"title": "email", "settings": {"subject": "...", "to": "...", "sender": "..."}},
        ]
}
```
