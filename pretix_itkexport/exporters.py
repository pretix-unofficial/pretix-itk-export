import locale
from collections import defaultdict

from pretix.base.models.orders import Order
from pretix_paymentdibs.payment import DIBS

# Make Python locale aware (and use LC_ALL from environment)
locale.setlocale(locale.LC_ALL, '')




class Exporter():
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
    index_psp = headers.index('PSP-element')
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

            artskonto = meta_data['Artskonto'] if 'Artskonto' in meta_data else None
            psp = meta_data['PSP'] if 'PSP' in meta_data else None
            psp_artskonto = meta_data['PSP_Artskonto'] if 'PSP_Artskonto' in meta_data else None
            amount = order.total

            row = [None] * len(self.headers)
            row[self.index_debit_credit] = 'debet'
            row[self.index_artskonto] = psp_artskonto
            row[self.index_psp] = psp
            row[self.index_amount] = self.formatAmount(amount)
            row[self.index_text] = 'Eventbilletordre: {0}, {1:%Y-%m-%d %H:%M}'.format(DIBS.get_order_id(order), order.payment_date)
            rows.append(row)

            # We have to copy the row for some reason …
            row = list(row)
            row[self.index_debit_credit] = 'kredit'
            row[self.index_artskonto] = artskonto
            row[self.index_psp] = None
            rows.append(row)

        return rows


class PaidOrdersGroupedExporter(PaidOrdersExporter):
    def loadData(self, **kwargs):
        orders = super().loadData(**kwargs)

        grouped_orders = defaultdict(list)
        for order in orders:
            meta_data = order.event.meta_data
            artskonto = meta_data['Artskonto'] if 'Artskonto' in meta_data else None
            psp = meta_data['PSP'] if 'PSP' in meta_data else None
            psp_artskonto = meta_data['PSP_Artskonto'] if 'PSP_Artskonto' in meta_data else None

            grouped_orders[(artskonto, None)].append(order)
            grouped_orders[(psp_artskonto, psp)].append(order)

        return grouped_orders

    def formatData(self, data, **kwargs):

        rows = []
        rows.append(self.headers)

        for [psp, artskonto], orders in data.items():
            amount = sum([order.total for order in orders])

            row = [None] * len(self.headers)
            row[self.index_artskonto] = artskonto
            row[self.index_psp] = psp
            row[self.index_debit_credit] = 'debet' if psp is None else 'kredit'
            row[self.index_amount] = self.formatAmount(amount)
            row[self.index_text] = __name__
            rows.append(row)

        return rows
