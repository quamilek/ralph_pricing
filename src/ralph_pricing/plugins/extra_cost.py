# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import decimal

from ralph.util import plugin, api_pricing
from ralph_pricing.models import ExtraCost, ExtraCostType, Venture


def update_extra_cost(data, date):
    cost_type, created = ExtraCostType.objects.get_or_create(name=data['type'])
    venture, created = Venture.objects.get_or_create(
        venture_id=data['venture_id'],
        defaults={'name': data['venture']},
    )
    extracost, created = ExtraCost.objects.get_or_create(
        start=data['start'],
        end=data['end'] if data['end'] else datetime.date(2048, 10, 24),
        type=cost_type,
        price=decimal.Decimal(data['cost'] / 30.5),
        pricing_venture=venture,
    )
    return created


@plugin.register(chain='pricing', requires=['never run'])
def extra_cost(**kwargs):

    date = kwargs['today']
    count = sum(
        update_extra_cost(data, date) for data in api_pricing.get_extra_cost()
    )
    return True, '%d new extracosts' % count, kwargs
