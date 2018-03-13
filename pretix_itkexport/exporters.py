from collections import defaultdict

from pretix.base.models.orders import Order


class EventExporter():
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
