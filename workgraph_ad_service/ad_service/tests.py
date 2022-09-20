from django.test import Client
from rest_framework.test import APITestCase
import os
import yaml
from py2neo import Graph
from ad_service.utils.security import encrypt
from ad_service.ad_integration.onboard_and_update import ADIntegration
import ad_service.utils.config as constants
from unittest.mock import Mock, patch
from ad_service.utils.queue import get_node_dict, get_relation_data_dict, get_relation_dict


class ADValue:
    def __init__(self, key):
        self.value = key


class ADOnboardTest(APITestCase):
    # setUp and tearDown are called before and after each test function
    def setUp(self):
        pass

    def tearDown(self):
        self._delete_nodes(label=constants.AD_PROFILE_LABELS[0])
        self._delete_nodes(label=constants.PERSON_LABELS[0])
        self._delete_nodes(label=constants.COMPANY_LABELS[0])

    def __init__(self, *args, **kwargs):
        super(ADOnboardTest, self).__init__(*args, **kwargs)
        with open(os.getcwd() + '/ad_secrets.yaml') as stream:
            secrets = yaml.load(stream)
        self.ad_url = secrets['AD_URL']
        self.ad_username = secrets['AD_USERNAME']
        self.ad_password = secrets['AD_PASSWORD']
        self.ad_search_base = secrets['AD_SEARCH_BASE']
        self.url = "/api/ad_integration/"
        self.group_id = 1
        self.graph = Graph(constants.TEST_GRAPH_URL, bolt=constants.GRAPH_BOLT)

        self.test_ad_integration = ADIntegration('test', 'test', 'test', 'test', constants.TEST_GRAPH_URL,
                                                 constants.TEST_QUEUE_URL + 'v2/', self.group_id)
        self.client = Client()
        self.entry = {
            constants.AD_TITLE: ADValue('title'),
            constants.AD_USERNAME: ADValue('sAMAccountName'),
            constants.AD_PRINCIPAL_NAME: ADValue('userPrincipalName'),
            constants.AD_GUID: ADValue('objectGUID'),
            constants.AD_COMPANY: ADValue('company'),
            constants.AD_PHONE_NUMBER: ADValue('mobile'),
            constants.AD_COUNTRY: ADValue('UAE'),
            constants.AD_CITY: ADValue('Dubai'),
            constants.AD_DISTINGUISHED_NAME: ADValue('distinguishedName'),
            constants.AD_EMAIL: ADValue('test@test.com'),
            constants.AD_FIRST_NAME: ADValue(''),
            constants.AD_LAST_NAME: ADValue('surname '),
            constants.AD_NAME: ADValue('first last'),
            constants.AD_MANAGER: ADValue('manager'),
            constants.AD_DIRECT_REPORTS: ADValue(['1', '2']),
            constants.AD_MEMBER_OF: ADValue('memberOf'),
            constants.AD_WHEN_CREATED: ADValue('whenCreated'),
        }
        self._delete_nodes(label=constants.AD_PROFILE_LABELS[0])
        self._delete_nodes(label=constants.PERSON_LABELS[0])
        self._delete_nodes(label=constants.COMPANY_LABELS[0])

    def _delete_nodes(self, label):
        query = "match (n:{0}) detach delete n".format(label)
        self.graph.run(query)

    def _get_all_nodes(self, label):
        query = "match (n:{0}) return n".format(label)
        nodes = []
        for record in self.graph.run(query):
            nodes.append(record[0])
        return nodes

    def _get_all_relations(self, from_label, to_label, relation_name):
        query = "match (n:{0})-[r:{1}]->(m:{2}) return r".format(from_label, relation_name, to_label)
        relation = []
        for record in self.graph.run(query):
            relation.append(record[0])
        return relation

    def test_onboard_invalid_password(self):
        # tests when password cant be decrypted
        payload = {
            "ad_url": self.ad_url,
            "ad_username": self.ad_username,
            "ad_password": "wrong",
            "ad_search_base": self.ad_search_base,
            "graph_url": "graph_url",
            "queue_url": "queue_url"
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 400)

    def test_onboard_incorrect_password(self):
        # tests when credentials are wrong
        payload = {
            "ad_url": self.ad_url,
            "ad_username": self.ad_username,
            "ad_password": encrypt('wrong').decode('utf-8'),
            "ad_search_base": self.ad_search_base,
            "graph_url": "graph_url",
            "queue_url": "queue_url"
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 400)

        payload["ad_url"] = '1.1.1.1'
        payload["ad_password"] = self.ad_password
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 400)

    def test_fill_name_if_blank(self):
        ad_first_name, ad_last_name = ADIntegration._fill_name_if_blank('', '', 'first last')

        self.assertEqual(ad_first_name, 'first')
        self.assertEqual(ad_last_name, 'last')

    def test_populate(self):
        self.test_ad_integration._populate(self.entry)

        expected_result = {
            'firstName': 'first',
            'lastName': 'surname',
            'primaryEmail': 'test@test.com',
            'adPrincipleName': 'userPrincipalName',
            'adUsername': 'sAMAccountName',
            'title': 'title',
            'adDistinguishedName': 'distinguishedName',
            'adGuid': 'objectGUID',
            'company': 'company',
            'phone': 'mobile',
            'personalWebsite': '',
            'location': 'Dubai, UAE',
            'division': '',
            'department': '',
            'directReports': ['1', '2'],
            'manager': 'manager',
        }
        keys_to_del = [key for key in self.test_ad_integration.data_to_send[0] if 'Time' in key]
        for key in keys_to_del:
            del self.test_ad_integration.data_to_send[0][key]
        self.assertDictEqual(self.test_ad_integration.data_to_send[0], expected_result)

    def test_populate_ad_profile_nodes(self):
        self.test_ad_integration._populate(self.entry)
        self.test_ad_integration._populate_ad_profile_nodes()
        ad_profiles = self._get_all_nodes(constants.AD_PROFILE_LABELS[0])
        self.assertEqual(len(ad_profiles), 1)

    def test_populate_user_nodes(self):
        self.test_ad_integration._populate(self.entry)
        self.test_ad_integration._populate_user_nodes()
        people = self._get_all_nodes(constants.PERSON_LABELS[0])
        self.assertEqual(len(people), 1)

    def test_populate_user_ad_profile_relations(self):
        self.test_ad_integration._populate(self.entry)
        self.test_ad_integration._populate_user_nodes()
        self.test_ad_integration._populate_ad_profile_nodes()
        self.test_ad_integration._populate_user_ad_profile_relations()
        relation = self._get_all_relations(from_label=constants.PERSON_LABELS[0],
                                           to_label=constants.AD_PROFILE_LABELS[0],
                                           relation_name=constants.PERSON_AD_PROFILE_RELATION)
        self.assertEqual(len(relation), 1)

    def test_populate_company_node(self):
        self.test_ad_integration._populate_company_node()
        company = self._get_all_nodes(constants.COMPANY_LABELS[0])
        self.assertEqual(len(company), 1)

    def test_populate_user_company_relations(self):
        self.test_ad_integration._populate(self.entry)
        self.test_ad_integration._populate_user_nodes()
        self.test_ad_integration._populate_company_node()
        self.test_ad_integration._populate_user_company_relations()
        relation = self._get_all_relations(from_label=constants.PERSON_LABELS[0],
                                           to_label=constants.COMPANY_LABELS[0],
                                           relation_name=constants.PERSON_COMPANY_RELATION)
        self.assertEqual(len(relation), 1)

    def test_ad_last_update_time(self):
        self.test_ad_integration._update_company_ad_last_fetch_time()
        ad_instance = self._get_all_nodes(constants.AD_INSTANCE_LABELS[0])
        self.assertEqual(len(ad_instance), 1)

    def test_ad_update(self):
        self.test_ad_integration._populate(self.entry)
        self.test_ad_integration._populate_ad_profile_nodes()
        new_phone = 'new_phone'
        self.entry[constants.AD_PHONE_NUMBER] = ADValue(new_phone)
        self.test_ad_integration.data_to_send = []
        self.test_ad_integration.unique_email_tracker = {}
        self.test_ad_integration._populate(self.entry)
        self.test_ad_integration._set_last_update_time_of_changed_fields()
        self.assertEqual(self.test_ad_integration.data_to_send[0]['phone'], new_phone)

    def test_populate_keeping_email_unique(self):
        self.test_ad_integration._populate(self.entry)
        self.test_ad_integration._populate(self.entry)
        self.assertEqual(len(self.test_ad_integration.data_to_send), 1)

        self.entry[constants.AD_EMAIL] = ADValue('new_email')
        self.test_ad_integration._populate(self.entry)
        self.assertEqual(len(self.test_ad_integration.data_to_send), 2)

        self.test_ad_integration.data_to_send = []
        self.test_ad_integration.unique_email_tracker = {}

        new_phone = 'new_phone'
        self.entry[constants.AD_WHEN_CREATED] = ADValue(2)
        self.test_ad_integration._populate(self.entry)
        self.entry[constants.AD_WHEN_CREATED] = ADValue(1)
        self.entry[constants.AD_PHONE_NUMBER] = ADValue(new_phone)
        self.test_ad_integration._populate(self.entry)
        self.assertEqual(self.test_ad_integration.data_to_send[0]['phone'], new_phone)

    @patch('ad_service.ad_integration.onboard_and_update.Connection')
    def test_get_ldap_data(self, mock_connection):
        entry = self.entry

        class Entry:
            def __init__(self, entry):
                self.entry = entry

            @property
            def __dict__(self):
                return self.entry

        class ADConnection:
            def __init__(self):
                self.entries = [Entry(entry)]
                self.search_calls = 0
                self.result = {'controls': {'1.2.840.113556.1.4.319': {'value': {'cookie': ''}}}}

            def search(self, *args, **kwargs):
                if self.search_calls == 0:
                    self.result['controls']['1.2.840.113556.1.4.319']['value']['cookie'] = 'test'
                else:
                    self.result['controls']['1.2.840.113556.1.4.319']['value']['cookie'] = ''
                self.search_calls += 1

        # mock_connection.return_value = Mock()
        mock_connection.return_value = ADConnection()
        self.test_ad_integration._get_ldap_data()
        self.assertEqual(len(self.test_ad_integration.data_to_send), 1)
