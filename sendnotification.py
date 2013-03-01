import logging
import os
import json
from collections import OrderedDict


class SendNotificationException(Exception):
    pass


class SendNotificationConf(OrderedDict):
    def __init__(self):
        super(SendNotificationConf, self).__init__()


class SendNotification(object):
    """Send a notification"""

    def __init__(self, auto_conf=True, conf=None):
        if auto_conf:
            self.auto_conf(conf)
        else:
            self.conf = SendNotificationConf()

    def auto_conf(self, conf):
        if conf:
            self.conf_path = conf
        else:
            self.conf_path = os.path.join(os.path.expanduser('~'),
                '.{}'.format(os.path.splitext(os.path.basename(__file__))[0]))

        try:
            conf = json.loads(open(self.conf_path).read())
        except IOError:
            error = 'Can\'t find json config file %s' % (self.conf_path,)
            logging.error(error)
            raise SendNotificationException(error)
        except ValueError:
            error = 'Invalid json config file'
            logging.error(error)
            raise SendNotificationException(error)

        self.conf = SendNotificationConf()
        for service in conf['services']:
            self.conf[service['title']] = service['settings']

    def validate_service_settings(self, service, settings_needed, settings_optional):
        service_settings = self.conf[service]
        valid_settings = settings_needed + settings_optional
        # Make sure all needed settings are set
        for setting in settings_needed:
            if setting not in service_settings or not service_settings[setting].strip():
                error = 'Missing setting for {}, {}'.format(service, setting)
                logging.error(error)
                raise SendNotificationException(error)
        # Don't allow any unwanted settings
        for setting in service_settings:
            if setting not in valid_settings:
                error = 'Unknown setting for {}, {}'.format(service, setting)
                logging.error(error)
                raise SendNotificationException(error)

    def validate_conf(self):
        # Validate that at least one service exists
        if len(self.conf) == 0:
            error = 'Missing services, at least one is needed'
            logging.error(error)
            raise SendNotificationException(error)

        for service in self.conf:
            if service not in ('notifikationnu', 'pushover', 'email'):
                error = 'Invalid service, {}'.format(service)
                logging.error(error)
                raise SendNotificationException(error)

            if service == 'notifikationnu':
                self.validate_service_settings(
                    service,
                    settings_needed=('api_key', 'notification_id'),
                    settings_optional=('category', 'event')
                )
            elif service == 'pushover':
                self.validate_service_settings(
                    service,
                    settings_needed=('app_token', 'api_key'),
                    settings_optional=('title',)
                )
            elif service == 'email':
                self.validate_service_settings(
                    service,
                    settings_needed=('subject', 'to'),
                    settings_optional=('sender',)
                )

    def send_notification(self, message, interval=None):
        """Send a notification, everything must be setup. Try to send through
        all configured services"""

        message = message.strip()
        if not message:
            raise SendNotificationException('Message can not be empty')

        self.validate_conf()

        send_success = False
        for service in self.conf:
            if service == 'notifikationnu':
                try:
                    self.send_notifikationnu(message=message, interval=interval, **self.conf['notifikationnu'])
                    send_success = True
                    break
                except Exception, e:
                    logging.error('Notifikation.nu failed. {}'.format(e))
                    continue
            elif service == 'pushover':
                try:
                    self.send_pushover(message=message, interval=interval, **self.conf['pushover'])
                    send_success = True
                    break
                except Exception, e:
                    logging.error('Pushover failed. {}'.format(e))
                    continue
            elif service == 'email':
                try:
                    self.send_email(message=message, interval=interval, **self.conf['email'])
                    send_success = True
                    break
                except Exception, e:
                    logging.error('Email failed. {}'.format(e))
                    continue

        if not send_success:
            error = 'No notification could be sent'
            logging.error(error)
            raise SendNotificationException(error)

    def check_interval(self, service, interval, notification):
        from hashlib import sha1
        import redis

        interval_key = '{}:{}'.format(
            os.path.splitext(os.path.basename(__file__))[0],
            sha1(''.join([service, str(interval)] + [str(x) for x in notification.values()])).hexdigest())

        r = redis.StrictRedis()
        if r.get(interval_key):
            logging.debug('Notification not sent. Interval set to {} sec, interval has not passed since last notification'.format(interval))
            return False
        else:
            logging.debug('Notification interval set to {} sec, no earlier notification sent'.format(interval))
            r.set(interval_key, 1)
            r.expire(interval_key, interval)
            return True

    def send_notifikationnu(self, api_key, notification_id, message, interval=None, category=None, event=None):
        # Notification
        notification = {
            'api_key': api_key,
            'notification_id': int(notification_id),
            'message': message,
        }
        if category:
            notification['category'] = category
        if event:
            notification['event'] = event

        logging.debug('Notifikation.nu sending notification {}'.format(notification))

        # Check notification interval
        if interval and not self.check_interval('notifikationnu', interval, notification):
            return False

        del(notification['api_key'])

        # Send Notifikation.nu notification
        from notifikation_nu import NotifikationNu
        notifikation_nu = NotifikationNu(api_key)
        notifikation_nu.send_notification(**notification)

        logging.debug('Notifikation.nu notification sent')
        return True

    def send_pushover(self, app_token, api_key, message, interval=None, title=None):
        # Notification
        notification = {
            'app_token': app_token,
            'api_key': api_key,
            'message': message,
        }
        if title:
            notification['title'] = title

        logging.debug('Pushover sending notification {}'.format(notification))

        # Check notification interval
        if interval and not self.check_interval('pushover', interval, notification):
            return False

        # Fix args
        notification['token'] = notification['app_token']
        notification['user'] = notification['api_key']
        del(notification['app_token'], notification['api_key'])

        # Send Pushover notification
        import requests
        r = requests.post('https://api.pushover.net/1/messages.json', notification)
        if r.status_code != 200:
            raise SendNotificationException(r.text)

        logging.debug('Pushover notification sent')
        return True

    def send_email(self, subject, to, message, interval=None, sender=None):
        # Notification
        notification = {
            'subject': subject,
            'to': to,
            'message': message,
        }
        if sender:
            notification['sender'] = sender

        logging.debug('Email sending notification {}'.format(notification))

        # Check notification interval
        if interval and not self.check_interval('email', interval, notification):
            return False

        # Send email notification
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to

        s = smtplib.SMTP('localhost')
        s.sendmail(sender, [to], msg.as_string())
        s.quit()

        logging.debug('Email notification sent')
        return True
