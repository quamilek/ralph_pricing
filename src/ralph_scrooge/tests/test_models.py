# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime

from django.test import TestCase

from ralph_scrooge import models
from ralph_scrooge.tests.models import History, HistoricalHistory
from ralph_scrooge.tests.utils.factory import (
    DailyPricingObjectFactory,
    PricingServiceFactory,
    ServiceEnvironmentFactory,
    UsageTypeFactory,
    WarehouseFactory,
)


class TestHistory(TestCase):
    def test_history_flow(self):
        current_now = datetime.datetime.now()
        obj = History(field1=11, field2='aa')
        obj.save()
        # check historical record
        self.assertEquals(obj.history.count(), 1)
        obj1 = obj.history.most_recent()
        self.assertEquals(obj1.field1, 11)
        self.assertEquals(obj1.field2, 'aa')

        history1 = obj.history.all()[:1].get()
        self.assertGreater(history1.active_from, current_now)
        self.assertEquals(history1.active_to, datetime.datetime.max)

        current_now = datetime.datetime.now()
        # change obj
        obj.field1 = 12
        obj.save()

        # check historical record
        self.assertEquals(obj.history.count(), 2)
        obj2 = obj.history.most_recent()
        self.assertEquals(obj2.field1, 12)
        self.assertEquals(obj2.field2, 'aa')

        history2, history1 = obj.history.all()[:2]
        self.assertEquals(history1.active_to, history2.active_from)
        self.assertEquals(history2.active_to, datetime.datetime.max)

    def test_history_without_changes(self):
        obj = History(field1=11, field2='aa')
        obj.save()

        # check historical record
        self.assertEquals(obj.history.count(), 1)
        obj.field1 = 11
        obj.save()

        self.assertEquals(obj.history.count(), 1)

    def test_history_delete(self):
        obj = History(field1=11, field2='aa')
        obj.save()
        obj_id = obj.pk
        # check historical record
        self.assertEquals(obj.history.count(), 1)

        obj.delete()

        self.assertEquals(HistoricalHistory.objects.count(), 1)
        history1 = HistoricalHistory.objects.all()[:1].get()
        self.assertEquals(history1.id, obj_id)
        self.assertLess(history1.active_to, datetime.datetime.now())


class TestModelDiff(TestCase):
    def test_obj_diff(self):
        obj = History(field1=11, field2='b')
        obj.save()

        # changes "without changes"
        obj.field1 = 11
        self.assertFalse(obj.has_changed)

        # real changes
        obj.field2 = 'vvv'
        self.assertTrue(obj.has_changed)
        self.assertEquals(obj.diff, {'field2': ('b', 'vvv')})

    def test_obj2dict(self):
        obj = History(field1=11, field2='b')
        self.assertEquals(obj._dict, {'field1': 11, 'field2': 'b', 'id': None})


class TestPricingService(TestCase):
    def _set_sample_usages(self):
        # 3 Pricing Services (1 tested and dependent from others)
        # usage types:
        self.ps1, self.ps2, self.ps3 = PricingServiceFactory.create_batch(3)
        se1 = ServiceEnvironmentFactory(service__pricing_service=self.ps1)
        se2 = ServiceEnvironmentFactory(service__pricing_service=self.ps1)

        ut1, ut2, ut3 = UsageTypeFactory.create_batch(3, usage_type='SU')

        models.ServiceUsageTypes(
            usage_type=ut1,
            pricing_service=self.ps2,
            start=datetime.date(2013, 10, 1),
            end=datetime.date(2013, 10, 30),
            percent=50,
        ).save()
        models.ServiceUsageTypes(
            usage_type=ut2,
            pricing_service=self.ps2,
            start=datetime.date(2013, 10, 1),
            end=datetime.date(2013, 10, 30),
            percent=50,
        ).save()
        models.ServiceUsageTypes(
            usage_type=ut3,
            pricing_service=self.ps3,
            start=datetime.date(2013, 10, 1),
            end=datetime.date(2013, 10, 30),
            percent=100,
        ).save()

        # sample usages
        models.DailyUsage(
            daily_pricing_object=DailyPricingObjectFactory(),
            type=ut1,
            date=datetime.date(2013, 10, 3),
            service_environment=se1,
            value=100,
        ).save()
        models.DailyUsage(
            daily_pricing_object=DailyPricingObjectFactory(),
            type=ut2,
            date=datetime.date(2013, 10, 20),
            service_environment=se1,
            value=100,
        ).save()
        models.DailyUsage(
            daily_pricing_object=DailyPricingObjectFactory(),
            type=ut1,
            date=datetime.date(2013, 10, 28),
            service_environment=se2,
            value=100,
            warehouse=WarehouseFactory(),
        ).save()
        models.DailyUsage(
            daily_pricing_object=DailyPricingObjectFactory(),
            type=ut3,
            date=datetime.date(2013, 10, 3),
            service_environment=se2,
            value=100,
        ).save()

    def test_get_dependent_services(self):
        self._set_sample_usages()
        result = self.ps1.get_dependent_services(
            date=datetime.date(2013, 10, 3),
        )
        self.assertEquals(set(result), set([self.ps2, self.ps3]))

    def test_get_dependent_services_subset(self):
        self._set_sample_usages()
        result = self.ps1.get_dependent_services(
            date=datetime.date(2013, 10, 28),
        )
        self.assertEquals(set(result), set([self.ps2]))

    def test_get_dependent_services_empty(self):
        self._set_sample_usages()
        result = self.ps1.get_dependent_services(
            date=datetime.date(2013, 11, 30)
        )
        self.assertEquals(set(result), set())