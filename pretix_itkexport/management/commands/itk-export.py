import csv
import sys
import datetime
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand, CommandError
from pretix.base.models.orders import Order

class Command(BaseCommand):
    help = 'Exports stuff'

    def add_arguments(self, parser):
        parser.add_argument('--starttime', nargs='?', type=str)
        parser.add_argument('--endtime', nargs='?', type=str)

    def handle(self, *args, **options):
        start_of_month = datetime.date.today().replace(day=1)
        end_of_month = start_of_month + relativedelta(months=1)
        
        self.stdout.write(self.style.SUCCESS(start_of_month))
        self.stdout.write(self.style.SUCCESS(end_of_month))

        starttime = start_of_month if options['starttime'] is None else datetime.datetime.strptime(options['starttime'], '%Y-%m-%d')
        endtime = end_of_month if options['endtime'] is None else datetime.datetime.strptime(options['endtime'], '%Y-%m-%d')

        writer = csv.writer(self.stdout)

        orders = Order.objects.all()

        for order in orders:
            writer.writerow([order.id, starttime, endtime])
