from collections import defaultdict

from django.template.defaultfilters import floatformat
from django.utils.translation import ugettext_lazy as _
from pretix.base.models.log import LogEntry
from pretix.base.models.orders import Order, OrderPayment, OrderRefund
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
        payments = self.loadPayments(**kwargs)
        refunds = self.loadRefunds(**kwargs)
        cash_payments = self.loadCashPayments(**kwargs)
        return self.formatData(payments, refunds, cash_payments, **kwargs)

    def loadPayments(self, **kwargs):
        return []

    def loadRefunds(self, **kwargs):
        return []

    def loadCashPayments(self, **kwargs):
        return []

    def formatData(self, payments, refunds, cash_payments, **kwargs):
        return payments


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

    def loadPayments(self, **kwargs):
        payment_filter = {
            'order__event__organizer__in': self.organizers,
            'state__in': [OrderPayment.PAYMENT_STATE_CONFIRMED, OrderPayment.PAYMENT_STATE_REFUNDED],
            'provider': 'dibs',
        }
        if 'starttime' in kwargs:
            payment_filter['payment_date__gte'] = kwargs['starttime']
        if 'endtime' in kwargs:
            payment_filter['payment_date__lt'] = kwargs['endtime']

        payments = OrderPayment.objects.filter(**payment_filter).order_by('payment_date').select_related('order', 'order__event')
        return payments

    def loadRefunds(self, **kwargs):
        refund_filter = {
            'order__event__organizer__in': self.organizers,
            'state__in': [OrderRefund.REFUND_STATE_DONE],
            'provider': 'dibs',
        }
        if 'starttime' in kwargs:
            refund_filter['payment_date__gte'] = kwargs['starttime']
        if 'endtime' in kwargs:
            refund_filter['payment_date__lt'] = kwargs['endtime']

        refunds = OrderRefund.objects.filter(**refund_filter).order_by('execution_date').select_related('order', 'order__event', 'payment')
        return refunds

    def loadCashPayments(self, **kwargs):
        payment_filter = {
            'order__event__organizer__in': self.organizers,
            'state__in': [OrderPayment.PAYMENT_STATE_CONFIRMED, OrderPayment.PAYMENT_STATE_REFUNDED],
            'provider': 'cash',
        }
        if 'starttime' in kwargs:
            payment_filter['payment_date__gte'] = kwargs['starttime']
        if 'endtime' in kwargs:
            payment_filter['payment_date__lt'] = kwargs['endtime']

        payments = OrderPayment.objects.filter(**payment_filter).order_by('payment_date').select_related('order', 'order__event')
        return payments

    def formatData(self, payments, refunds, cash_payments, **kwargs):
        raise Exception(self.__class__.__name__+'.formatData not implemented')

    def localizeCardType(self, card_type):
        if DIBS.CARD_TYPE_CREDIT == card_type:
            return _('credit')
        if DIBS.CARD_TYPE_DEBIT == card_type:
            return _('debit')
        return card_type

    def getCardType(self, payment):
        return DIBS.get_payment_card_type(payment) if DIBS.identifier == payment.provider else None


class PaidOrdersLineExporter(PaidOrdersExporter):
    def loadPayments(self, **kwargs):
        payments = super().loadPayments(**kwargs)

        grouped_orders = defaultdict(list)
        for payment in payments:
            meta_data = payment.order.event.meta_data
            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None
            card_type = self.getCardType(payment)
            order_id = DIBS.get_order_id(payment)

            # Create two lines for double-entry bookkeeping and group orders by
            # artskonto, psp-element, cardtype and order id.
            grouped_orders[(self.debit_artskonto, None, card_type, order_id)].append(payment)
            grouped_orders[(self.credit_artskonto, pspelement, None, order_id)].append(payment)

        return grouped_orders

    def loadRefunds(self, **kwargs):
        refunds = super().loadRefunds(**kwargs)

        grouped_orders = defaultdict(list)
        for refund in refunds:
            meta_data = refund.order.event.meta_data
            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None
            card_type = self.getCardType(refund.payment)
            order_id = DIBS.get_order_id(refund.payment)

            # Create two lines for double-entry bookkeeping and group orders by
            # artskonto, psp-element, cardtype and order id.
            grouped_orders[(self.debit_artskonto, None, card_type, order_id)].append(refund)
            grouped_orders[(self.credit_artskonto, pspelement, None, order_id)].append(refund)

        return grouped_orders

    def formatData(self, payments, refunds, cash_payments, **kwargs):
        rows = []
        rows.append(self.headers)

        for [artskonto, pspelement, card_type, order_id], payments in payments.items():
            amount = sum([payment.amount for payment in payments])

            row = [None] * len(self.headers)
            row[self.index_artskonto] = artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_debit_credit] = 'kredit' if pspelement is not None else 'debet'
            row[self.index_amount] = self.formatAmount(amount)
            order_ids = ', '.join([DIBS.get_order_id(payment) for payment in payments])
            if card_type is not None:
                row[self.index_text] = _('Ticket sale ({card_type}): {order_ids}').format(card_type=self.localizeCardType(card_type), order_ids=order_ids)
            else:
                row[self.index_text] = _('Ticket sale: {order_ids}').format(order_ids=order_ids)

            rows.append(row)

        for [artskonto, pspelement, card_type, order_id], refunds in refunds.items():
            amount = sum([refund.amount for refund in refunds])

            row = [None] * len(self.headers)
            row[self.index_artskonto] = artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_debit_credit] = 'debet' if pspelement is not None else 'kredit'
            row[self.index_amount] = self.formatAmount(amount)
            order_ids = ', '.join([DIBS.get_order_id(refund.payment) for refund in refunds])
            if card_type is not None:
                row[self.index_text] = _('Ticket refund ({card_type}): {order_ids}').format(card_type=self.localizeCardType(card_type), order_ids=order_ids)
            else:
                row[self.index_text] = _('Ticket refund: {order_ids}').format(order_ids=order_ids)

            rows.append(row)

        for payment in cash_payments:
            meta_data = payment.order.event.meta_data
            pspelement = meta_data['PSP'] if 'PSP' in meta_data else None

            row = [None] * len(self.headers)
            row[self.index_artskonto] = self.cash_artskonto
            row[self.index_debit_credit] = 'debet'
            row[self.index_amount] = self.formatAmount(payment.order.total)
            row[self.index_text] = _('Cash payment ({user}): {order_id}').format(order_id=DIBS.get_order_id(payment), user=payment.order.email)

            rows.append(row)

            row = list(row)
            row[self.index_artskonto] = self.credit_artskonto
            row[self.index_pspelement] = pspelement
            row[self.index_debit_credit] = 'kredit'

            rows.append(row)

        return rows
