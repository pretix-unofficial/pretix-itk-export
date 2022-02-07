import csv
import io
import re
from datetime import date, datetime, timedelta

import dateparser
import django.conf
import pytz
import yaml
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from django_scopes import scope
from pretix_itkexport.exporters import (
    PaidOrdersLineExporter
)

from pretix.base.models import Organizer


class Command(BaseCommand):
    help = 'Exports stuff'

    date_format = '%Y-%m-%d'

    def add_arguments(self, parser):
        parser.add_argument('--starttime', nargs='?', type=str)
        parser.add_argument('--endtime', nargs='?', type=str)
        parser.add_argument('--period', nargs='?', type=str,
                            help='current-year, previous-year, '
                                 'current-month, previous-month, '
                                 'current-week, previous-week, '
                                 'current-day, today, '
                                 'previous-day, yesterday'
                                 ', previous-week[±days]'
                            )
        parser.add_argument('--debit-artskonto', nargs=1, type=str)
        parser.add_argument('--credit-artskonto', nargs=1, type=str)
        parser.add_argument('--cash-artskonto', nargs=1, type=str)
        parser.add_argument('--organizer', action='append', nargs='+', type=str, help='Organizer slugs to select (can be used multiple times)')
        parser.add_argument('--recipient', action='append', nargs='?', type=str, help='Email adress to send export result to (can be used multiple times)')
        parser.add_argument('--debug', action='store_true')
        parser.add_argument('--verbose', action='store_true')

    def handle(self, *args, **options):
        try:
            from django.conf import settings
            translation.activate(settings.LANGUAGE_CODE)

            debug = options['debug']
            verbose = debug or options['verbose']

            settings = self.getSettings(options)

            if debug:
                print('options:')
                print(yaml.dump(options, default_flow_style=False))

                print('settings:')
                print(yaml.dump(settings, default_flow_style=False))

            organizers = list(Organizer.objects.filter(slug__in=options['organizer']))
            options['organizer'] = organizers
            with scope(organizer=organizers):
                exporter = PaidOrdersLineExporter(options)
                data = exporter.getData(**settings)

            recipient_list = settings['recipient_list']

            if recipient_list:
                now = datetime.now()
                filename = 'eventbillet-{}.csv'.format(now.strftime('%Y%m%dT%H%M'))
                if 'starttime' in settings:
                    filename = 'eventbillet-{:%Y%m%d}'.format(settings['starttime'])
                    if 'endtime' in settings:
                        filename += '-{:%Y%m%d}'.format(settings['endtime'])
                    filename += '.csv'

                output = io.StringIO()
                writer = csv.writer(output, dialect='excel', delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                for row in data:
                    writer.writerow(row)
                content = output.getvalue()
                output.close()

                subject = _('Order export from {site_name}').format(site_name=django.conf.settings.PRETIX_INSTANCE_NAME)
                if 'starttime' in settings:
                    starttime = settings['starttime']
                    endtime = settings['endtime'] if 'endtime' in settings else now
                    subject += ' ({:%Y-%m-%d}–{:%Y-%m-%d})'.format(starttime, endtime)
                body = content
                from_email = settings['from_email']

                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=recipient_list,
                    attachments=[
                        (filename, content, 'text/csv'),
                    ]
                )

                email.send(fail_silently=False)

                if verbose:
                    print(content)
                    print('Sent to: {}'.format(', '.join(recipient_list)))
                    print('Subject: {}'.format(subject))

            else:
                writer = csv.writer(self.stdout)
                for row in data:
                    writer.writerow(row)
        except Exception as e:
            raise e if debug else CommandError(e)

    def getSettings(self, options):
        settings = {}

        for name in options:
            if options[name] is not None:
                settings[name] = options[name]

        if 'period' in settings:
            (starttime, endtime) = self.getPeriod(settings['period'])

            settings['starttime'] = starttime.isoformat()
            settings['endtime'] = endtime.isoformat()

        if 'starttime' in settings:
            d = dateparser.parse(settings['starttime'])
            if d is None:
                raise CommandError('Error parsing starttime: {}'.format(settings['starttime']))
            if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
                d = pytz.utc.localize(d)
            settings['starttime'] = d
        if 'endtime' in settings:
            d = dateparser.parse(settings['endtime'])
            if d is None:
                raise CommandError('Error parsing endtime: {}'.format(settings['endtime']))
            if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
                d = pytz.utc.localize(d)
            settings['endtime'] = d

        settings['recipient_list'] = settings['recipient'] if 'recipient' in settings else None
        settings['from_email'] = settings['sender'] if 'sender' in settings else None

        return settings

    def getPeriod(self, period):
        starttime = None
        endtime = None

        today = dateparser.parse(date.today().strftime('%Y-%m-%d'))
        # Monday in the current week
        this_monday = today - timedelta(days=today.weekday())

        if period == 'current-year':
            starttime = dateparser.parse(datetime.today().strftime('%Y-01-01'))
            endtime = dateparser.parse('in 1 year', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'previous-year':
            start_of_year = dateparser.parse(datetime.today().strftime('%Y-01-01'))
            starttime = dateparser.parse('1 year ago', settings={'RELATIVE_BASE': start_of_year})
            endtime = dateparser.parse('in 1 year', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'current-month':
            starttime = dateparser.parse(datetime.today().strftime('%Y-%m-01'))
            endtime = dateparser.parse('in 1 month', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'previous-month':
            start_of_month = dateparser.parse(datetime.today().strftime('%Y-%m-01'))
            starttime = dateparser.parse('1 month ago', settings={'RELATIVE_BASE': start_of_month})
            endtime = dateparser.parse('in 1 month', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'current-week':
            starttime = this_monday
            endtime = dateparser.parse('in 1 week', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif re.match(r'previous-week([+-]\d+)?', period):
            match = re.match(r'previous-week([+-]\d+)?', period)
            offset = int(match.group(1)) if match.group(1) is not None else 0

            start_of_week = this_monday
            starttime = dateparser.parse('Monday', settings={'RELATIVE_BASE': start_of_week})
            endtime = dateparser.parse('in 1 week', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

            if offset != 0:
                starttime += timedelta(days=offset)
                endtime += timedelta(days=offset)

        elif period == 'current-day' or period == 'today':
            starttime = dateparser.parse('00:00:00')
            endtime = dateparser.parse('in 1 day', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'previous-day' or period == 'yesterday':
            starttime = dateparser.parse('yesterday 00:00:00')
            endtime = dateparser.parse('in 1 day', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        else:
            raise CommandError('Invalid period: {}'.format(period))

        # https://docs.djangoproject.com/en/1.11/topics/i18n/timezones/
        starttime = pytz.utc.localize(starttime)
        endtime = pytz.utc.localize(endtime)

        return (starttime, endtime)
