import csv
import datetime

import pytz
from dateutil import parser, relativedelta
from django.core.management.base import BaseCommand, CommandError
from pretix_itkexport.exporters import EventExporter


class Command(BaseCommand):
    help = 'Exports stuff'

    date_format = '%Y-%m-%d'

    def add_arguments(self, parser):
        parser.add_argument('--starttime', nargs='?', type=str)
        parser.add_argument('--endtime', nargs='?', type=str)

    def handle(self, *args, **options):
        start_of_month = datetime.datetime.today().replace(day=1)
        end_of_month = start_of_month + relativedelta.relativedelta(months=1)

        try:
            starttime = start_of_month if options['starttime'] is None else parser.parse(options['starttime'])
        except:
            raise CommandError('Error parsing starttime: %s' % options['starttime'])
        starttime = pytz.utc.localize(starttime)
        try:
            endtime = end_of_month if options['endtime'] is None else parser.parse(options['endtime'])
        except:
            raise CommandError('Error parsing starttime: %s' % options['endtime'])
        endtime = pytz.utc.localize(endtime)

        exporter = EventExporter()
        data = exporter.getData(starttime=starttime, endtime=endtime)

        writer = csv.writer(self.stdout)
        for index, item in enumerate(data):
            if index == 0:
                writer.writerow(item.keys())
            writer.writerow(item.values())
