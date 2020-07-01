# sendnotification

A small CLI tool and python lib for sending notifications using different
services.

Supported services

- Pushover
- Email

Supports interval setting for only sending notification every X seconds to
prevent sending to many notifications against a specific service. This
requires `redis`.

## Send notification with config

```python
sn = SendNotification()
sn.send_notification('Notification message')
````

## Add interval, only send a notification every interval sec

```python
sn.send_notification('Notification message', interval=3600)
```

## Manual setup without config

```python
sn = SendNotification(auto_conf=False)
sn.conf = {'pushover': {'app_token': '...', 'api_key': '...'}}
```

## Pushover notification

```python
sn.send_pushover(app_token, api_key, message, interval=None, title=None)
```

## Email notification

```python
sn.send_email(subject, to, message, interval=None, sender=None)
```

## Send from command line (uses config)

```shell
sendnotification [-i/--interval 3600] message
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
