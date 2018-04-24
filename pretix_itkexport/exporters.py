import locale
import re
from collections import defaultdict

import django.conf
from django.utils.translation import ugettext_lazy as _
from pretix.base.models.orders import Order
from pretix_paymentdibs.payment import DIBS

# Make Python locale aware (and use LC_ALL from environment)
locale.setlocale(locale.LC_ALL, '')


class Exporter():
    settings = dict()

    # banken skal debiteres.
    debit_artskonto = None

    # Driftskal krediteres hvis der er tale om en indtægt
    credit_artskonto = None

    def __init__(self):
        if hasattr(django.conf.settings, 'ITK_EXPORT'):
            self.settings = django.conf.settings.ITK_EXPORT

        if 'credit_artskonto' not in self.settings:
            raise Exception('Missing "credit_artskonto" in settings')
        if 'debit_artskonto' not in self.settings:
            raise Exception('Missing "debit_artskonto" in settings')

        self.debit_artskonto = self.settings['debit_artskonto']
        self.credit_artskonto = self.settings['credit_artskonto']

    def info(self):
        # Remove trailing "Exporter"
        name = re.sub(r'Exporter$', '', self.__class__.__name__)
        # Split by uppercase letter (excluding first) and downcase
        name = re.sub(r'(?<!^)([A-Z])', lambda m: ' ' + m.groups(1)[0].lower(), name)
        doc = re.sub(r'^\s+', '', self.__doc__)
        return name + '\n\n' + doc

    @staticmethod
    def formatAmount(amount):
        return locale.format('%.2f', amount)

    def getData(self, **kwargs):
        data = self.loadData(**kwargs)
        return self.formatData(data, **kwargs)

    def loadData(self, **kwargs):
        return None

    def formatData(self, data, **kwargs):
        return data


class EventExporter(Exporter):
    def getData(self, **kwargs):
        order_filter = {
            'status': Order.STATUS_PAID
        }
        if 'starttime' in kwargs:
            order_filter['datetime__gte'] = kwargs['starttime']
        if 'endtime' in kwargs:
            order_filter['datetime__lt'] = kwargs['endtime']

        orders = Order.objects.filter(**order_filter).order_by('datetime')

        grouped_orders = defaultdict(list)
        for order in orders:
            grouped_orders[order.event].append(order)

        data = []

        for event, orders in grouped_orders.items():
            revenue = sum([order.total for order in orders])
            expenses = 0.0
            audience = event.meta_data['Audience'] if 'Audience' in event.meta_data else None

            data.append({
                'organizer': event.organizer,
                'name': event.name,
                'datetime': event.date_from,
                'revenue': revenue,
                'expenses': expenses,
                'audience': audience
            })

        return data


class PaidOrdersExporter(Exporter):
    """
    Exports paid orders.
    """

    headers = [
        'Artskonto',
        'Omkostningssted',
        'PSP-element',
        'Profitcenter',
        'Ordre',
        'Debet/kredit',
        'Beløb',
        'Næste agent',
        'Tekst',
        'Betalingsart',
        'Påligningsår',
        'Betalingsmodtagernr.',
        'Betalingsmodtagernr.kode',
        'Ydelsesmodtagernr.',
        'Ydelsesmodtagernr.kode',
        'Ydelsesperiode fra',
        'Ydelsesperiode til',
        'Oplysningspligtnr.',
        'Oplysningspligtmodtagernr.kode',
        'Oplysningspligtkode',
        'Netværk',
        'Operation',
        'Mængde',
        'Mængdeenhed',
        'Referencenøgle'
    ]

    index_artskonto = headers.index('Artskonto')
    index_pspelement = headers.index('PSP-element')
    index_debit_credit = headers.index('Debet/kredit')
    index_amount = headers.index('Beløb')
    index_text = headers.index('Tekst')

    def loadData(self, **kwargs):
        order_filter = {
            'status': Order.STATUS_PAID,
            'total__gt': 0
        }
        if 'starttime' in kwargs:
            order_filter['payment_date__gte'] = kwargs['starttime']
        if 'endtime' in kwargs:
            order_filter['payment_date__lt'] = kwargs['endtime']

        orders = Order.objects.filter(**order_filter).order_by('payment_date')

        return orders

    def formatData(self, data, **kwargs):
        rows = []
        rows.append(self.headers)

        for order in data:
            meta_data = order.event.meta_data

            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None
            amount = order.total

            row = [None] * len(self.headers)
            row[self.index_debit_credit] = 'kredit'
            row[self.index_artskonto] = self.credit_artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_amount] = self.formatAmount(amount)
            row[self.index_text] = _('Ticket sale: {order_id}').format(order_id=DIBS.get_order_id(order))
            rows.append(row)

            # We have to copy the row for some reason …
            row = list(row)
            row[self.index_debit_credit] = 'debet'
            row[self.index_artskonto] = self.debit_artskonto
            row[self.index_pspelement] = None
            rows.append(row)

        return rows


class PaidOrdersGroupedExporter(PaidOrdersExporter):
    """
    Exports paid orders grouped by (artskonto, pspelement).
    """

    def loadData(self, **kwargs):
        orders = super().loadData(**kwargs)

        grouped_orders = defaultdict(list)
        for order in orders:
            meta_data = order.event.meta_data
            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None

            grouped_orders[(self.debit_artskonto, None)].append(order)
            grouped_orders[(self.credit_artskonto, pspelement)].append(order)

        return grouped_orders

    def formatData(self, data, **kwargs):
        rows = []
        rows.append(self.headers)

        for [artskonto, pspelement], orders in data.items():
            amount = sum([order.total for order in orders])

            row = [None] * len(self.headers)
            row[self.index_artskonto] = artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_debit_credit] = 'kredit' if pspelement is not None else 'debet'
            row[self.index_amount] = self.formatAmount(amount)
            row[self.index_text] = _('Ticket sale: {order_ids}').format(order_ids=', '.join([DIBS.get_order_id(order) for order in orders]))

            rows.append(row)

        return rows
