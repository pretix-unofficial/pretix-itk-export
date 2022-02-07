from collections import defaultdict

from django.template.defaultfilters import floatformat
from django.utils.translation import ugettext_lazy as _
from pretix.base.models.log import LogEntry
from pretix.base.models.orders import Order
from pretix_paymentdibs.payment import DIBS


class Exporter():
    # banken skal debiteres.
    debit_artskonto = None

    # Driftskal krediteres hvis der er tale om en indtægt
    credit_artskonto = None

    cash_artskonto = None

    def __init__(self, options):
        if 'credit_artskonto' not in options:
            raise Exception('Missing "credit_artskonto" in settings')
        if 'debit_artskonto' not in options:
            raise Exception('Missing "debit_artskonto" in settings')
        if 'cash_artskonto' not in options:
            raise Exception('Missing "cash_artskonto" in settings')

        self.organizers = options['organizer']
        self.debit_artskonto = options['debit_artskonto']
        self.credit_artskonto = options['credit_artskonto']
        self.cash_artskonto = options['cash_artskonto']

    @staticmethod
    def formatAmount(amount):
        return floatformat(amount, 2)

    def getData(self, **kwargs):
        paid_orders = self.loadPaidOrders(**kwargs)
        refunded_orders = self.loadRefundedOrders(**kwargs)
        cash_orders = self.loadCashOrders(**kwargs)
        return self.formatData(paid_orders, refunded_orders, cash_orders, **kwargs)

    def loadPaidOrders(self, **kwargs):
        return []

    def loadRefundedOrders(self, **kwargs):
        return []

    def loadCashOrders(self, **kwargs):
        return []

    def formatData(self, paid_orders, refunded_orders, cash_orders, **kwargs):
        return paid_orders


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

    def loadPaidOrders(self, **kwargs):
        order_filter = {
            'event__organizer__in': self.organizers,
            'status__in': [Order.STATUS_PAID, Order.STATUS_REFUNDED],
            'payment_provider': 'dibs',
            'total__gt': 0
        }
        if 'starttime' in kwargs:
            order_filter['payment_date__gte'] = kwargs['starttime']
        if 'endtime' in kwargs:
            order_filter['payment_date__lt'] = kwargs['endtime']

        orders = Order.objects.filter(**order_filter).order_by('payment_date')

        return orders

    def loadRefundedOrders(self, **kwargs):
        # https://docs.djangoproject.com/en/2.0/topics/db/sql/#adding-annotations
        order_table_name = Order.objects.model._meta.db_table
        logentry_table_name = LogEntry.objects.model._meta.db_table
        sql = 'select o.*, l.datetime refund_date from ' + order_table_name + ' o ' \
            ' inner join ' + logentry_table_name + ' l on l.object_id = o.id and l.action_type = %(action_type)s' \
            ' where o.status in %(status)s and o.payment_provider = %(payment_provider)s and o.total > 0' \
            ' and %(starttime)s <= l.datetime and l.datetime < %(endtime)s'
        # todo: filter by organizer
        parameters = {
            'action_type': 'pretix.event.order.refunded',
            'status': [Order.STATUS_REFUNDED],
            'payment_provider': 'dibs',
            'starttime': kwargs['starttime'] if 'starttime' in kwargs else '2001-01-01',
            'endtime': kwargs['endtime'] if 'endtime' in kwargs else '2087-01-01'
        }
        orders = Order.objects.raw(sql, parameters)

        return orders

    def loadCashOrders(self, **kwargs):
        order_filter = {
            'event__organizer__in': self.organizers,
            'status__in': [Order.STATUS_PAID, Order.STATUS_REFUNDED],
            'payment_provider': 'cash',
            'total__gt': 0
        }
        if 'starttime' in kwargs:
            order_filter['payment_date__gte'] = kwargs['starttime']
        if 'endtime' in kwargs:
            order_filter['payment_date__lt'] = kwargs['endtime']

        orders = Order.objects.filter(**order_filter).order_by('payment_date')

        return orders

    def formatData(self, paid_orders, refunded_orders, cash_orders, **kwargs):
        raise Exception(self.__class__.__name__+'.formatData not implemented')

    def localizeCardType(self, card_type):
        if DIBS.CARD_TYPE_CREDIT == card_type:
            return _('credit')
        if DIBS.CARD_TYPE_DEBIT == card_type:
            return _('debit')
        return card_type

    def getCardType(self, order):
        return DIBS.get_payment_card_type(order) if DIBS.identifier == order.payment_provider else None


class PaidOrdersLineExporter(PaidOrdersExporter):
    def loadPaidOrders(self, **kwargs):
        orders = super().loadPaidOrders(**kwargs)

        grouped_orders = defaultdict(list)
        for order in orders:
            meta_data = order.event.meta_data
            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None
            card_type = self.getCardType(order)
            order_id = DIBS.get_order_id(order)

            # Create two lines for double-entry bookkeeping and group orders by
            # artskonto, psp-element, cardtype and order id.
            grouped_orders[(self.debit_artskonto, None, card_type, order_id)].append(order)
            grouped_orders[(self.credit_artskonto, pspelement, None, order_id)].append(order)

        return grouped_orders

    def loadRefundedOrders(self, **kwargs):
        orders = super().loadRefundedOrders(**kwargs)

        grouped_orders = defaultdict(list)
        for order in orders:
            meta_data = order.event.meta_data
            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None
            card_type = self.getCardType(order)
            order_id = DIBS.get_order_id(order)

            # Create two lines for double-entry bookkeeping and group orders by
            # artskonto, psp-element, cardtype and order id.
            grouped_orders[(self.debit_artskonto, None, card_type, order_id)].append(order)
            grouped_orders[(self.credit_artskonto, pspelement, None, order_id)].append(order)

        return grouped_orders

    def formatData(self, paid_orders, refunded_orders, cash_orders, **kwargs):
        rows = []
        rows.append(self.headers)

        for [artskonto, pspelement, card_type, order_id], orders in paid_orders.items():
            amount = sum([order.total for order in orders])

            row = [None] * len(self.headers)
            row[self.index_artskonto] = artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_debit_credit] = 'kredit' if pspelement is not None else 'debet'
            row[self.index_amount] = self.formatAmount(amount)
            order_ids = ', '.join([DIBS.get_order_id(order) for order in orders])
            if card_type is not None:
                row[self.index_text] = _('Ticket sale ({card_type}): {order_ids}').format(card_type=self.localizeCardType(card_type), order_ids=order_ids)
            else:
                row[self.index_text] = _('Ticket sale: {order_ids}').format(order_ids=order_ids)

            rows.append(row)

        for [artskonto, pspelement, card_type, order_id], orders in refunded_orders.items():
            amount = sum([order.total for order in orders])

            row = [None] * len(self.headers)
            row[self.index_artskonto] = artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_debit_credit] = 'debet' if pspelement is not None else 'kredit'
            row[self.index_amount] = self.formatAmount(amount)
            order_ids = ', '.join([DIBS.get_order_id(order) for order in orders])
            if card_type is not None:
                row[self.index_text] = _('Ticket refund ({card_type}): {order_ids}').format(card_type=self.localizeCardType(card_type), order_ids=order_ids)
            else:
                row[self.index_text] = _('Ticket refund: {order_ids}').format(order_ids=order_ids)

            rows.append(row)

        for order in cash_orders:
            meta_data = order.event.meta_data
            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None

            row = [None] * len(self.headers)
            row[self.index_artskonto] = self.cash_artskonto
            row[self.index_debit_credit] = 'debet'
            row[self.index_amount] = self.formatAmount(order.total)
            row[self.index_text] = _('Cash payment ({user}): {order_id}').format(order_id=DIBS.get_order_id(order), user=order.email)

            rows.append(row)

            row = list(row)
            row[self.index_artskonto] = self.credit_artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_debit_credit] = 'kredit'

            rows.append(row)

        return rows
