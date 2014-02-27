# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import mock
from collections import OrderedDict
from dateutil import rrule
from decimal import Decimal as D

from django.test import TestCase
from django.utils.translation import ugettext_lazy as _

from ralph_pricing import models
from ralph_pricing.plugins.reports.usage import UsagePlugin


class TestUsageBasePlugin(TestCase):
    def setUp(self):
        # usage types
        self.usage_type = models.UsageType(
            name='UsageType1',
            symbol='ut1',
            by_warehouse=False,
            by_cost=False,
            type='BU',
        )
        self.usage_type.save()
        self.usage_type_cost_wh = models.UsageType(
            name='UsageType2',
            symbol='ut2',
            by_warehouse=True,
            by_cost=True,
            type='BU',
        )
        self.usage_type_cost_wh.save()

        self.service_usage_type1 = models.UsageType(
            name='ServiceUsageType1',
            symbol='sut1',
            type='SU',
        )
        self.service_usage_type1.save()
        self.service_usage_type2 = models.UsageType(
            name='ServiceUsageType2',
            # symbol='sut2',
            type='SU',
        )
        self.service_usage_type2.save()

        # warehouses
        self.warehouse1 = models.Warehouse(
            name='Warehouse1',
            show_in_report=True,
        )
        self.warehouse1.save()
        self.warehouse2 = models.Warehouse(
            name='Warehouse2',
            show_in_report=True,
        )
        self.warehouse2.save()
        self.warehouses = models.Warehouse.objects.all()

        # service
        self.service = models.Service(
            name='Service1'
        )
        self.service.save()
        self.service.base_usage_types.add(
            self.usage_type_cost_wh,
            self.usage_type
        )
        models.ServiceUsageTypes(
            usage_type=self.service_usage_type1,
            service=self.service,
            start=datetime.date(2013, 10, 1),
            end=datetime.date(2013, 10, 15),
            percent=30,
        ).save()
        models.ServiceUsageTypes(
            usage_type=self.service_usage_type2,
            service=self.service,
            start=datetime.date(2013, 10, 1),
            end=datetime.date(2013, 10, 15),
            percent=70,
        ).save()
        models.ServiceUsageTypes(
            usage_type=self.service_usage_type1,
            service=self.service,
            start=datetime.date(2013, 10, 16),
            end=datetime.date(2013, 10, 30),
            percent=40,
        ).save()
        models.ServiceUsageTypes(
            usage_type=self.service_usage_type2,
            service=self.service,
            start=datetime.date(2013, 10, 16),
            end=datetime.date(2013, 10, 30),
            percent=60,
        ).save()
        self.service.save()

        # ventures
        self.venture1 = models.Venture(
            venture_id=1,
            name='V1',
            is_active=True,
            service=self.service,  # venture is providing service
        )
        self.venture1.save()
        self.venture2 = models.Venture(
            venture_id=2,
            name='V2',
            is_active=True,
            service=self.service,  # venture is providing service
        )
        self.venture2.save()
        self.venture3 = models.Venture(venture_id=3, name='V3', is_active=True)
        self.venture3.save()
        self.venture4 = models.Venture(venture_id=4, name='V4', is_active=True)
        self.venture4.save()
        self.service_ventures = list(self.service.venture_set.all())
        self.not_service_ventures = list(models.Venture.objects.exclude(id__in=[i.id for i in self.service_ventures]))
        self.ventures = models.Venture.objects.all()

        # daily usages of base type
        # ut1:
        #   venture1: 10
        #   venture2: 20
        # ut2:
        #   venture1: 20 (half in warehouse1, half in warehouse2)
        #   venture2: 40 (half in warehouse1, half in warehouse2)
        start = datetime.date(2013, 10, 8)
        end = datetime.date(2013, 10, 22)
        for i, ut in enumerate(models.UsageType.objects.filter(type='BU'), start=1):
            for j, day in enumerate(rrule.rrule(rrule.DAILY, dtstart=start, until=end), start=1):
                for k, venture in enumerate(models.Venture.objects.all(), start=1):
                    daily_usage = models.DailyUsage(
                        date=day,
                        pricing_venture=venture,
                        value=10 * i * k,
                        type=ut,
                    )
                    if ut.by_warehouse:
                        daily_usage.warehouse = self.warehouses[j % len(self.warehouses)]
                    daily_usage.save()

        # usage prices
        dates = [
            (datetime.date(2013, 10, 5), datetime.date(2013, 10, 12)),
            (datetime.date(2013, 10, 13), datetime.date(2013, 10, 17)),
            (datetime.date(2013, 10, 18), datetime.date(2013, 10, 25)),
        ]
        # (real cost/price, forecast cost/price)
        ut_prices_costs = [
            (self.usage_type, [(10, 50), (20, 60), (30, 70)]),
            (self.usage_type_cost_wh, [
                [(3600, 2400), (5400, 5400), (4800, 12000)],  # warehouse1
                [(3600, 5400), (3600, 1200), (7200, 3600)],  # warehouse2
            ]),
        ]

        def add_usage_price(usage_type, prices_costs, warehouse=None):
            for daterange, price_cost in zip(dates, prices_costs):
                start, end = daterange
                usage_price = models.UsagePrice(
                    type=usage_type,
                    start=start,
                    end=end,
                )
                if warehouse is not None:
                    usage_price.warehouse = warehouse
                if usage_type.by_cost:
                    usage_price.cost = price_cost[0]
                    usage_price.forecast_cost = price_cost[1]
                else:
                    usage_price.price = price_cost[0]
                    usage_price.forecast_price = price_cost[1]
                usage_price.save()

        for ut, prices in ut_prices_costs:
            if ut.by_warehouse:
                for i, prices_wh in enumerate(prices):
                    warehouse = self.warehouses[i]
                    add_usage_price(ut, prices_wh, warehouse)
            else:
                add_usage_price(ut, prices)

        # usage of service resources
        start = datetime.date(2013, 10, 8)
        end = datetime.date(2013, 10, 22)
        for i, ut in enumerate(models.UsageType.objects.filter(type='SU'), start=1):
            for j, day in enumerate(rrule.rrule(rrule.DAILY, dtstart=start, until=end), start=1):
                for k, venture in enumerate(self.not_service_ventures, start=1):
                    daily_usage = models.DailyUsage(
                        date=day,
                        pricing_venture=venture,
                        value=10 * i * k,
                        type=ut,
                    )
                    daily_usage.save()

    def test_get_usage_type_cost(self):
        result = UsagePlugin._get_total_cost_by_warehouses(
            start=datetime.date(2013, 10, 10),
            end=datetime.date(2013, 10, 20),
            usage_type=self.usage_type,
            ventures=self.service_ventures,
            forecast=False,
        )
        # 10-12: usage: 3 * (10 + 20) = 90; cost: 90 * 10 = 900
        # 13-17: usage: 5 * (10 + 20) = 150; cost: 150 * 20 = 3000
        # 18-20: usage: 3 * (10 + 20) = 90; cost = 90 * 30 = 2700
        # total: usage: 330; cost: 6600
        self.assertEquals(result, [330.0, D('6600')])

    def test_get_total_cost(self):
        result = UsagePlugin.total_cost(
            start=datetime.date(2013, 10, 10),
            end=datetime.date(2013, 10, 20),
            usage_type=self.usage_type,
            ventures=self.service_ventures,
            forecast=False,
        )
        self.assertEquals(result, D('6600'))

    def test_get_usage_type_cost_forecast(self):
        result = UsagePlugin._get_total_cost_by_warehouses(
            start=datetime.date(2013, 10, 10),
            end=datetime.date(2013, 10, 20),
            usage_type=self.usage_type,
            ventures=[self.venture1],
            forecast=True,
        )
        # 10-12: usage: 3 * 10 = 30; cost: 30 * 50 = 1500
        # 13-17: usage: 5 * 10 = 50; cost: 50 * 60 = 3000
        # 18-20: usage: 3 * 10 = 30; cost = 30 * 70 = 2100
        # total: usage: 110; cost: 6600
        self.assertEquals(result, [110.0, D('6600')])

    def test_get_usage_type_cost_by_cost(self):
        result = UsagePlugin._get_total_cost_by_warehouses(
            start=datetime.date(2013, 10, 10),
            end=datetime.date(2013, 10, 20),
            usage_type=self.usage_type_cost_wh,
            ventures=self.service_ventures,
            forecast=False,
        )
        # 5-12: (usages are from 8 to 12)
        #   warehouse1:
        #               usage: 2 * (20 + 40 + 60 + 80) = 400;
        #               cost: 3600;
        #               price = 3600 / 400 = 9;
        #   warehouse2:
        #               usage: 3 * (20 + 40 + 60 + 80) = 600;
        #               cost: 3600;
        #               price = 3600 / 600 = 6;
        # 13-17:
        #   warehouse1:
        #               usage: 3 * (20 + 40 + 60 + 80) = 600;
        #               cost: 5400
        #               price = 5400 / 600 = 9;
        #   warehouse2:
        #               usage: 2 * (20 + 40 + 60 + 80) = 400;
        #               cost: 3600
        #               price = 3600 / 400 = 9;
        # 18-25: (usages are from 18 to 22)
        #   warehouse1:
        #               usage: 2 * (20 + 40 + 60 + 80) = 400;
        #               cost: 4800
        #               price = 4800 / 400 = 12;
        #   warehouse2:
        #               usage: 3 * (20 + 40 + 60 + 80) = 600;
        #               cost: 7200
        #               price = 7200 / 600 = 12;

        # 10-12:
        #   warehouse1: usage: 1 * (20 + 40) = 60;
        #               cost: 60 * 9 = 540
        #   warehouse2: usage: 2 * (20 + 40) = 120;
        #               cost: 120 * 6 = 720
        # 13-17:
        #   warehouse1: usage: 3 * (20 + 40) = 180;
        #               cost: 180 * 9 = 1620
        #   warehouse2: usage: 2 * (20 + 40) = 120;
        #               cost: 120 * 9 = 1080
        # 18-20:
        #   warehouse1: usage: 1 * (20 + 40) = 60;
        #               cost: 60 * 12 = 720
        #   warehouse2: usage: 2 * (20 + 40) = 120;
        #               cost: 120 * 12 = 1440
        # total:
        #   warehouse1: usage: 300; cost: 2880
        #   warehouse2: usage: 360; cost: 3240
        #   total: cost: 6840
        self.assertEquals(result, [300.0, D('2880'), 360.0, D('3240'), D('6120')])

    def test_get_usage_type_cost_by_cost_forecast(self):
        result = UsagePlugin._get_total_cost_by_warehouses(
            start=datetime.date(2013, 10, 10),
            end=datetime.date(2013, 10, 20),
            usage_type=self.usage_type_cost_wh,
            ventures=[self.venture1],
            forecast=True,
        )
        # 5-12: (usages are from 8 to 12)
        #   warehouse1:
        #               usage: 2 * (20 + 40 + 60 + 80) = 400;
        #               cost: 2400;
        #               price = 2400 / 400 = 6;
        #   warehouse2:
        #               usage: 3 * (20 + 40 + 60 + 80) = 600;
        #               cost: 5400;
        #               price = 5400 / 600 = 9;
        # 13-17:
        #   warehouse1:
        #               usage: 3 * (20 + 40 + 60 + 80) = 600;
        #               cost: 5400
        #               price = 5400 / 600 = 9;
        #   warehouse2:
        #               usage: 2 * (20 + 40 + 60 + 80) = 400;
        #               cost: 1200
        #               price = 1200 / 400 = 3;
        # 18-25: (usages are from 18 to 22)
        #   warehouse1:
        #               usage: 2 * (20 + 40 + 60 + 80) = 400;
        #               cost: 12000
        #               price = 12000 / 400 = 30;
        #   warehouse2:
        #               usage: 3 * (20 + 40 + 60 + 80) = 600;
        #               cost: 3600
        #               price = 3600 / 600 = 6;

        # 10-12:
        #   warehouse1: usage: 1 * 20 = 20;
        #               cost: 20 * 6 = 120
        #   warehouse2: usage: 2 * 20 = 40;
        #               cost: 40 * 9 = 360
        # 13-17:
        #   warehouse1: usage: 3 * 20 = 60;
        #               cost: 60 * 9 = 540
        #   warehouse2: usage: 2 * 20 = 40;
        #               cost: 40 * 3 = 120
        # 18-20:
        #   warehouse1: usage: 1 * 20 = 20;
        #               cost: 20 * 30 = 600
        #   warehouse2: usage: 2 * 20 = 40;
        #               cost: 40 * 6 = 240
        # total:
        #   warehouse1: usage: 100; cost: 1260
        #   warehouse2: usage: 120; cost: 720
        #   total: cost: 1980
        self.assertEquals(result, [100.0, D('1260'), 120.0, D('720'), D('1980')])
