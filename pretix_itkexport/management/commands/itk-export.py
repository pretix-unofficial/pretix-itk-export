import csv
import io
import re
from datetime import datetime

import dateparser
import django.conf
import pytz
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from pretix_itkexport.exporters import (
    EventExporter, PaidOrdersExporter, PaidOrdersGroupedExporter,
)


class Command(BaseCommand):
    help = 'Exports stuff'

    date_format = '%Y-%m-%d'

    exporter_classes = {
        'event': EventExporter,
        'paid_orders': PaidOrdersExporter,
        'paid_orders_grouped': PaidOrdersGroupedExporter
    }

    def add_arguments(self, parser):
        parser.add_argument('export_type', type=str, help=', '.join(Command.exporter_classes.keys()))
        parser.add_argument('--starttime', nargs='?', type=str)
        parser.add_argument('--endtime', nargs='?', type=str)
        parser.add_argument('--period', nargs='?', type=str, help='last-year, last-month, last-week, last-day')
        parser.add_argument('--recipients', nargs='?', type=str)

    def handle(self, *args, **options):
        settings = self.getSettings(options)

        export_type = settings['export_type']
        if export_type not in Command.exporter_classes:
            raise CommandError('Unknown export type: {}'.format(export_type))

        exporter = Command.exporter_classes[export_type]()
        data = exporter.getData(**settings)

        recipient_list = settings['recipient_list']

        if recipient_list:
            now = datetime.now()
            filename = 'eventbillet-{}.csv'.format(now.strftime('%Y%m%dT%H%M'))
            output = io.StringIO()
            writer = csv.writer(output, dialect='excel', delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for row in data:
                writer.writerow(row)
            content = output.getvalue()
            output.close()

            subject = 'Export from eventbillet ({})'.format(now.strftime('%Y-%m-%d %H:%M'))
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

            print(content)

        else:
            writer = csv.writer(self.stdout)
            for row in data:
                writer.writerow(row)

    def getSettings(self, options):
        settings = django.conf.settings.ITK_EXPORT.copy() if hasattr(django.conf.settings, 'ITK_EXPORT') else {}

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
            settings['starttime'] = d

        if 'endtime' in settings:
            d = dateparser.parse(settings['endtime'])
            if d is None:
                raise CommandError('Error parsing endtime: {}'.format(settings['endtime']))
            settings['endtime'] = d

        settings['recipient_list'] = re.split(r'\s*,\s*', settings['recipients']) if 'recipients' in settings else None
        settings['from_email'] = settings['sender'] if 'sender' in settings else None

        return settings

    def getPeriod(self, period):
        starttime = None
        endtime = None

        if period == 'last-year':
            start_of_year = dateparser.parse('January 1')
            starttime = dateparser.parse('1 year ago', settings={'RELATIVE_BASE': start_of_year})
            endtime = dateparser.parse('in 1 year', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'last-month':
            start_of_month = dateparser.parse(datetime.today().strftime('%Y-%m-01'))
            starttime = dateparser.parse('1 month ago', settings={'RELATIVE_BASE': start_of_month})
            endtime = dateparser.parse('in 1 month', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'last-week':
            starttime = dateparser.parse('Monday', settings={'RELATIVE_BASE': dateparser.parse('Monday')})
            endtime = dateparser.parse('in 1 week', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        elif period == 'last-day':
            starttime = dateparser.parse('yesterday 00:00:00')
            endtime = dateparser.parse('tomorrow', settings={'RELATIVE_BASE': starttime, 'PREFER_DATES_FROM': 'future'})

        else:
            raise CommandError('Invalid period: {}'.format(period))

        # https://docs.djangoproject.com/en/1.11/topics/i18n/timezones/
        starttime = pytz.utc.localize(starttime)
        endtime = pytz.utc.localize(endtime)

        return (starttime, endtime)
