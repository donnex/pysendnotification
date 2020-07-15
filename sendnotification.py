"""Send notification."""
import json
import logging
import os
from collections import OrderedDict


class SendNotificationError(Exception):
    """Send notification error."""

    pass


class SendNotificationConfig(OrderedDict):
    """Send notification config."""

    pass


class SendNotification:
    """Send notification."""

    SERVICES = ("email", "pushover")

    def __init__(self, config_file=None):
        """Send notification setup.

        config_file path to JSON config file. Set to False to disable reading
        of external config file for manual setup.
        """
        self.config = SendNotificationConfig()
        self.config_file = None

        # Config file path
        if config_file:
            self.config_file = config_file
        # No config file path, use file from homedir
        elif config_file is not False:
            self.config_file = os.path.join(
                os.path.expanduser("~"),
                f".{os.path.splitext(os.path.basename(__file__))[0]}",
            )

        # Read config file when set
        if self.config_file:
            self.config.update(self.read_config_file())

    def read_config_file(self):
        """Read and return parsed config file."""
        try:
            config = json.loads(open(self.config_file).read())
        except IOError:
            self.error(f"Unable to open JSON config file {self.config_file}")
        except ValueError:
            self.error("Invalid JSON config file")

        # Rewrite config and set config by service title
        enabled_services = []
        for service in config["services"]:
            config[service["title"]] = service["settings"]
            enabled_services.append(service["title"])
        config["services"] = enabled_services

        return config

    def validate_config(self):
        """Validate configuration."""
        if (
            not self.config.get("services")
            or len(self.config["services"]) == 0
        ):
            self.error("Missing services, at least one is needed")

        for service in self.config["services"]:
            if service not in self.SERVICES:
                self.error(f"Invalid service {service}")

            if service == "pushover":
                self.validate_service_settings(
                    service,
                    required_settings=("app_token", "api_key"),
                    optional_settings=("title",),
                )
            elif service == "email":
                self.validate_service_settings(
                    service,
                    required_settings=("subject", "to"),
                    optional_settings=("sender",),
                )

    def validate_service_settings(
        self, service, required_settings, optional_settings
    ):
        """Validate service settings."""
        service_settings = self.config[service]
        valid_settings = required_settings + optional_settings

        # Validate required settings
        for setting in required_settings:
            if (
                setting not in service_settings
                or not service_settings[setting].strip()
            ):
                self.error(f"Missing setting for {service} {setting}")

        # Do not allow unknown settings
        for setting in service_settings:
            if setting not in valid_settings:
                self.error(f"Unknown setting for {service} {setting}")

    def error(self, message):
        """Log error and raise exception."""
        logging.error(message)
        raise SendNotificationError(message)

    def send(self, message, interval=None):
        """Send notification.

        Will try to send notification to all configured services. If one
        fails the next service will be used.
        """
        self.validate_config()

        message = message.strip()
        if not message:
            self.error("Message can not be empty")

        send_success = False
        for service in self.config["services"]:
            logging.debug("Sending with service %s", service)

            if service == "pushover":
                try:
                    self.send_pushover(
                        message=message,
                        interval=interval,
                        **self.config[service],
                    )
                    send_success = True
                    break
                except Exception as e:
                    logging.error("Pushover failed: %s", e)
                    continue
            elif service == "email":
                try:
                    self.send_email(
                        message=message,
                        interval=interval,
                        **self.config[service],
                    )
                    send_success = True
                    break
                except Exception as e:
                    logging.error("Email failed: %s", e)
                    continue

        if not send_success:
            self.error("No notification could be sent")

        return True

    def check_interval(self, service, interval, notification):
        """Check interval for service notification.

        Return False if notification is not OK to send, the same notification
        has been sent in the last interval seconds.

        If notification is allowed to be sent the Redis key will be set
        with interval as expire time.
        """
        from hashlib import sha1
        import redis

        # Redis key with service, interval and notification data as dedupe key
        interval_key = "{}:{}".format(
            os.path.splitext(os.path.basename(__file__))[0],
            sha1(
                "".join(
                    [service, str(interval)]
                    + [str(x) for x in notification.values()]
                ).encode("utf-8")
            ).hexdigest(),
        )

        r = redis.Redis()

        # Interval match, do not allow new notification to be sent
        if r.get(interval_key):
            logging.debug(
                "Notification not sent. Interval has not passed since last "
                "notification"
            )
            return False

        # Set interval key
        logging.debug("Notification interval set to %s sec", interval)
        r.set(interval_key, 1)
        r.expire(interval_key, interval)

        return True

    def send_pushover(
        self, app_token, api_key, message, interval=None, title=None
    ):
        """Send notification with Pushover."""
        notification = {
            "app_token": app_token,
            "api_key": api_key,
            "message": message,
        }

        if title:
            notification["title"] = title

        logging.debug("Pushover sending notification %s", notification)

        # Check notification interval
        if interval and not self.check_interval(
            "pushover", interval, notification
        ):
            return False

        # Rewrite arguments
        notification["token"] = notification["app_token"]
        notification["user"] = notification["api_key"]
        del (notification["app_token"], notification["api_key"])

        # Pushover notification
        import requests
        from requests.adapters import HTTPAdapter
        from requests.packages.urllib3.util.retry import Retry

        # Setup requests retries
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)

        # Send notification
        response = http.post(
            "https://api.pushover.net/1/messages.json", notification, timeout=5
        )
        if response.status_code != 200:
            self.error(response.text)

        logging.debug("Pushover notification sent")

        return True

    def send_email(self, subject, to, message, interval=None, sender=None):
        """Send notification with email.

        Email will be sent to localhost.
        """
        notification = {
            "subject": subject,
            "to": to,
            "message": message,
        }

        if sender:
            notification["sender"] = sender

        logging.debug("Email sending notification %s", notification)

        # Check notification interval
        if interval and not self.check_interval(
            "email", interval, notification
        ):
            return False

        # Send email notification
        import smtplib
        from email.mime.text import MIMEText

        message = MIMEText(message)
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = to

        s = smtplib.SMTP("localhost")
        s.sendmail(sender, [to], message.as_string())
        s.quit()

        logging.debug("Email notification sent")

        return True
