# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import mock

from django.test import TestCase
from django.test.utils import override_settings

from ralph_scrooge.models import PRICING_OBJECT_TYPES
from ralph_scrooge.plugins.collect.ralph3_cloud_project import (
    get_unknown_service_env,
    save_tenant_info,
    save_daily_tenant_info,
    cloud_project as cloud_project_plugin,
    UnknownServiceEnvironmentNotConfiguredError,
)

from ralph_scrooge.tests.utils.factory import (
    ServiceEnvironmentFactory,
    TenantInfoFactory,
)

UNKNOWN_SERVICE_ENVIRONMENT = ('os-1', 'env1')
TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS = dict(
    UNKNOWN_SERVICES_ENVIRONMENTS={
        'ralph3_tenant': UNKNOWN_SERVICE_ENVIRONMENT
    },
)


class TestServiceCollectPlugin(TestCase):
    def setUp(self):
        ServiceEnvironmentFactory.reset_sequence()
        self.service_environment = ServiceEnvironmentFactory()
        self.unknown_service_environment = ServiceEnvironmentFactory(
            service__name=UNKNOWN_SERVICE_ENVIRONMENT[0],
            environment__name=UNKNOWN_SERVICE_ENVIRONMENT[1],
        )
        self.today = datetime.date(2014, 7, 1)

    def _get_sample_tenant(self):
        return {
            'id': '123456789',
            'service_env': {
                'environment': self.service_environment.environment.name,
                'service_uid': self.service_environment.service.ci_uid,
            },
            'name': 'sample_tenant',
            'remarks': 'qwerty',
        }

    def _compare_tenants(self, sample_tenant, tenant_info):
        self.assertEquals(tenant_info.ralph3_tenant_id, sample_tenant['id'])
        self.assertEquals(tenant_info.name, sample_tenant['name'])
        self.assertEquals(tenant_info.remarks, sample_tenant['remarks'])
        self.assertEquals(tenant_info.type_id, PRICING_OBJECT_TYPES.TENANT)

    def test_save_tenant_info(self):
        sample_tenant = self._get_sample_tenant()
        sample_tenant['service_env']['environment'] = (
            self.service_environment.environment.name
        )
        sample_tenant['service_env']['service_uid'] = (
            self.service_environment.service.ci_uid
        )
        created, tenant_info = save_tenant_info(
            sample_tenant,
            self.unknown_service_environment
        )
        self.assertTrue(created)
        self._compare_tenants(sample_tenant, tenant_info)
        self.assertEquals(
            tenant_info.service_environment,
            self.service_environment
        )

    def test_save_tenant_info_invalid_service_environment(self):
        sample_tenant = self._get_sample_tenant()
        sample_tenant['service_env']['environment'] = 'does_not_exist'
        sample_tenant['service_env']['service_uid'] = 'uid-xxx'
        created, tenant_info = save_tenant_info(
            sample_tenant,
            self.unknown_service_environment
        )
        self.assertTrue(created)
        self._compare_tenants(sample_tenant, tenant_info)
        self.assertEquals(
            tenant_info.service_environment,
            self.unknown_service_environment
        )

    def test_save_daily_tenant_info(self):
        tenant_info = TenantInfoFactory()
        sample_tenant = self._get_sample_tenant()
        result = save_daily_tenant_info(
            sample_tenant,
            tenant_info,
            self.today
        )
        self.assertEquals(result.tenant_info, tenant_info)
        self.assertEquals(result.pricing_object, tenant_info)
        self.assertEquals(result.date, self.today)
        self.assertEquals(
            result.service_environment,
            tenant_info.service_environment
        )

    @override_settings(**TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS)
    def test_get_tenant_unknown_service_environment(self):
        service_environment = ServiceEnvironmentFactory(
            service__ci_uid=UNKNOWN_SERVICE_ENVIRONMENT[0],
            environment__name=UNKNOWN_SERVICE_ENVIRONMENT[1],
        )
        self.assertEquals(
            service_environment,
            get_unknown_service_env()
        )

    @override_settings(**TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS)
    def test_get_tenant_unknown_service_invalid_config(self):
        with self.assertRaises(UnknownServiceEnvironmentNotConfiguredError):
            get_unknown_service_env()

    def test_get_tenant_unknown_service_not_configured(self):
        with self.assertRaises(UnknownServiceEnvironmentNotConfiguredError):
            get_unknown_service_env()

    @mock.patch('ralph_scrooge.plugins.collect.ralph3_cloud_project.get_cloud_provider_id')  # noqa
    @mock.patch('ralph_scrooge.plugins.collect.ralph3_cloud_project.get_from_ralph')  # noqa
    @mock.patch('ralph_scrooge.plugins.collect.ralph3_cloud_project.update_tenant')  # noqa
    @override_settings(**TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS)
    def test_cloud_project_plugin(
        self,
        update_tenant_mock,
        get_from_ralph_mock,
        get_cloud_provider_id_mock,
    ):
        unknown_service_environment = ServiceEnvironmentFactory(
            service__ci_uid=UNKNOWN_SERVICE_ENVIRONMENT[0],
            environment__name=UNKNOWN_SERVICE_ENVIRONMENT[1],
        )
        update_tenant_mock.return_value = True
        tenants_list = [self._get_sample_tenant()] * 5
        get_from_ralph_mock.return_value = tenants_list
        get_cloud_provider_id_mock.return_value = 1
        result = cloud_project_plugin(self.today)
        self.assertEquals(
            result,
            (True, '5 new tenants, 0 updated, 5 total')
        )
        self.assertEquals(update_tenant_mock.call_count, 5)
        update_tenant_mock.assert_any_call(
            tenants_list[0],
            self.today,
            unknown_service_environment,
        )

    @mock.patch('ralph_scrooge.plugins.collect.ralph3_cloud_project.get_unknown_service_env')  # noqa
    @override_settings(**TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS)
    def test_cloud_project_plugin_unknown_service_not_configured(
        self,
        get_unknown_service_env_mock
    ):
        get_unknown_service_env_mock.side_effect = (
            UnknownServiceEnvironmentNotConfiguredError()
        )
        result = cloud_project_plugin(self.today)
        self.assertEquals(
            result,
            (
                False,
                'Unknown service environment not configured for "tenant"',
            )
        )
