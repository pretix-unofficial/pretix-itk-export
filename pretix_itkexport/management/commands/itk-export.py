import csv
import datetime
import io
import re

import django.conf
import pytz
from dateutil import parser, relativedelta
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from pretix_itkexport.exporters import EventExporter


class Command(BaseCommand):
    help = 'Exports stuff'

    date_format = '%Y-%m-%d'

    def add_arguments(self, parser):
        parser.add_argument('--starttime', nargs='?', type=str)
        parser.add_argument('--endtime', nargs='?', type=str)
        parser.add_argument('--recipients', nargs='?', type=str)

    def handle(self, *args, **options):
        settings = self.getSettings(options)

        exporter = EventExporter()
        data = self.processData(exporter.getData(starttime=settings['starttime'], endtime=settings['endtime']))

        print(settings)

        recipient_list = settings['recipient_list']

        if recipient_list:
            now = datetime.datetime.now()
            filename = 'eventbillet-{}.csv'.format(now.strftime('%Y%m%dT%H%M'))
            output = io.StringIO()
            writer = csv.writer(output)
            for row in data:
                writer.writerow(row)
            content = output.getvalue()

            print(filename)
            print(content)

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

        else:
            writer = csv.writer(self.stdout)
            for row in data:
                writer.writerow(row)

    def processData(self, data):
        keys = ['organizer', 'name', 'datetime', 'revenue', 'expenses', 'audience']

        processed = []
        for index, item in enumerate(data):
            if index == 0:
                processed.append(keys)
            processed.append([item[key] for key in keys])

        return processed

    def getSettings(self, options):
        settings = django.conf.settings.ITK_EXPORT.copy() if hasattr(django.conf.settings, 'ITK_EXPORT') else {}
        for name in options:
            if options[name] is not None:
                settings[name] = options[name]

        start_of_month = datetime.datetime.today().replace(day=1)
        end_of_month = start_of_month + relativedelta.relativedelta(months=1)

        try:
            settings['starttime'] = pytz.utc.localize(parser.parse(settings['starttime']) if 'starttime' in settings else start_of_month)
        except Exception:
            raise CommandError('Error parsing starttime: %s' % settings['starttime'])

        try:
            settings['endtime'] = pytz.utc.localize(parser.parse(settings['endtime']) if 'endtime' in settings else end_of_month)
        except Exception:
            raise CommandError('Error parsing endtime: %s' % settings['endtime'])

        settings['recipient_list'] = re.split(r'\s*,\s*', settings['recipients']) if 'recipients' in settings else None
        settings['from_email'] = settings['sender']

        return settings
