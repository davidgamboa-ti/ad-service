import time
from py2neo import Graph
from ldap3 import Server, Connection, ALL, SUBTREE

from ad_service.utils import config
from ad_service.utils.queue import *
import ad_service.utils.graph as graph
import ad_service.utils.time as time
from ad_service.utils.time import get_milliseconds_since_epoch, time_now_in_ad_format


class ADIntegration:
    def __init__(self, ad_url, ad_username, ad_password, ad_search_base, graph_url, queue_url, group_id):
        """
        :param ad_url: Active-Directory LDAP Url
        :param ad_username: Active-Directory admin username
        :param ad_password: Active-Directory admin password
        :param ad_search_base: Active-Directory search base (eg.: DC=devfactory,DC=xyz)
        :param graph_url: Company workgraph url
        :param queue_url: Company queue url corresponding to workgraph
        """
        self.ad_url = ad_url
        self.ad_username = ad_username
        self.ad_password = ad_password
        self.ad_search_base = ad_search_base
        self.pagination_size = config.PAGINATION_SIZE  # Number of records to fetch per ldap request

        self.graph = Graph(graph_url)
        self.queue_url = queue_url
        self.logger = config.LOGGER
        self.group_id = group_id

        self.done = 0
        self.not_done = 0
        self.data_to_send = []
        self.unique_email_tracker = {}
        self.keys_to_track = ['title', 'phone', 'location', 'department']

    @staticmethod
    def _fill_name_if_blank(ad_first_name, ad_last_name, name):
        if ad_first_name == '':
            if name != '':
                ad_first_name = name.split()[0]
        if ad_last_name == '':
            if name != '':
                ad_last_name = ' '.join(name.split()[1:])
        return ad_first_name, ad_last_name

    @staticmethod
    def _get_location(city, country):
        if country != '' and city != '':
            location = city + ', ' + country
        elif country != '':
            location = country
        else:
            location = city
        return location

    @staticmethod
    def _get_direct_reports(direct_reports_key, entry):
        if direct_reports_key in entry.keys():
            if type(entry[direct_reports_key].value) == str:
                direct_reports = [entry[direct_reports_key].value]
            else:
                direct_reports = list(entry[direct_reports_key].value)
        else:
            direct_reports = ''
        return direct_reports

    def _populate(self, entry):
        """
        Take AD user data, parse it and populate data_to_send keeping email unique
        :param entry: AD user data
        """
        def check(ad_key):
            return '' if ad_key not in entry.keys() else entry[ad_key].value

        ad_distinguished_name = check(config.AD_DISTINGUISHED_NAME)

        try:
            ad_email = entry[config.AD_EMAIL].value.lower()
        except KeyError:
            self.not_done += 1
            return

        ad_first_name = check(config.AD_FIRST_NAME)
        ad_last_name = check(config.AD_LAST_NAME)
        name = check(config.AD_NAME)

        ad_first_name, ad_last_name = self._fill_name_if_blank(ad_first_name, ad_last_name, name)

        if ad_last_name == '' or any(char.isdigit() for char in ad_last_name) or \
                any(char.isdigit() for char in ad_first_name):
            self.not_done += 1
            return

        ad_title = check(config.AD_TITLE)
        ad_username = check(config.AD_USERNAME)
        ad_principle_name = check(config.AD_PRINCIPAL_NAME)
        ad_guid = check(config.AD_GUID)
        ad_company = check(config.AD_COMPANY)
        ad_phone_number = check(config.AD_PHONE_NUMBER)
        ad_personal_website = check(config.AD_PERSONAL_WEBSITE)
        division = check(config.AD_DIVISION)
        department = check(config.AD_DEPARTMENT)
        manager = check(config.AD_MANAGER)
        data_source = config.DATA_SOURCE

        country = check(config.AD_COUNTRY)
        city = check(config.AD_CITY)
        location = self._get_location(city, country)
        created_at = time.timestamp_to_integer(check(config.AD_WHEN_CREATED))

        direct_reports = self._get_direct_reports(config.AD_DIRECT_REPORTS, entry)
        member_type = "Individual Contributor"
        if len(direct_reports) > 0:
            member_type = "People Managers"

        member_data = {
            'first_name': ad_first_name.strip(),
            'last_name': ad_last_name.strip(),
            'primary_email': ad_email.strip(),
            'ad_principle_name': ad_principle_name,
            'ad_username': ad_username,
            'title': ad_title,
            'ad_distinguished_name': ad_distinguished_name,
            'ad_guid': ad_guid,
            'company': ad_company,
            'phone': ad_phone_number,
            'personal_website': ad_personal_website,
            'location': location,
            'division': division,
            'department': department,
            'direct_reports': direct_reports,
            'manager': manager,
            'last_update_time': get_milliseconds_since_epoch(),
            'data_source': data_source,
            'created_at': created_at
        }

        for key in self.keys_to_track:
            member_data[key +'_update_time'] = get_milliseconds_since_epoch()

        self._populate_keeping_email_unique(ad_email, entry, member_data)

    def _populate_keeping_email_unique(self, ad_email, entry, member_data):
        if ad_email in self.unique_email_tracker:
            # if multiple entries found for same email keep the earliest created record
            # (to ignore groups that get created with same email)
            if entry[config.AD_WHEN_CREATED].value < self.unique_email_tracker[ad_email]['created_at']:
                idx = self.unique_email_tracker[ad_email]['entry_idx']
                del self.data_to_send[idx]
                self.data_to_send.append(member_data)
                self.done += 1
        else:
            self.data_to_send.append(member_data)
            self.done += 1
            self.unique_email_tracker[ad_email] = {
                'created_at': entry[config.AD_WHEN_CREATED].value,
                'entry_idx': len(self.data_to_send) - 1
            }

    def _get_ldap_data(self):
        server = Server(self.ad_url, get_info=ALL)
        conn = Connection(server, self.ad_username, self.ad_password, auto_bind=True)
        logger.info("Starting ldap data fetch for AD_URL : " + self.ad_url)

        default_search_filter = config.AD_SEARCH_FILTER
        last_fetch_time = graph.get_ldap_last_fetch_time(self.graph, self.ad_url)
        logger.info("LDAP last_fetch_time: {0}".format(last_fetch_time))

        if last_fetch_time is not None:
            search_filter = '(&(whenChanged>=' + last_fetch_time + ')' + default_search_filter + ')'
        else:
            search_filter = default_search_filter

        conn.search(search_base=self.ad_search_base,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=['*'],
                    paged_size=self.pagination_size)

        entries = conn.entries
        for entry in entries:
            self._populate(entry.__dict__)

        logger.info(
            'Done : ' + str(self.done) + " || Not Done : " + str(self.not_done) + " for AD_URL: " + self.ad_url)

        cookie = conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie']
        while cookie:
            conn.search(search_base=self.ad_search_base,
                        search_filter=search_filter,
                        search_scope=SUBTREE,
                        attributes=['*'],
                        paged_size=self.pagination_size,
                        paged_cookie=cookie)
            cookie = conn.result['controls']['1.2.840.113556.1.4.319']['value']['cookie']

            entries = conn.entries
            for entry in entries:
                self._populate(entry.__dict__)

            logger.info(
                'Done : ' + str(self.done) + " || Not Done : " + str(self.not_done) + " for AD_URL: " + self.ad_url)

        logger.info("Finished ldap data fetch for AD_URL : " + self.ad_url)

    def _populate_user_ad_profile_relations(self):
        user_ad_profile_relation_data = []
        for data in self.data_to_send:
            user_ad_profile_relation_data.append(
                get_relation_data_dict(to_key_value=data[config.AD_PROFILE_PRIMARY_KEY],
                                       from_key_value=data[config.PERSON_PRIMARY_KEY],
                                       properties={
                                        'performed_at': data['created_at']
                                       }))
        chunks = [user_ad_profile_relation_data[i:i + config.QUEUE_CHUNK_SIZE] for i in
                  range(0, len(user_ad_profile_relation_data), config.QUEUE_CHUNK_SIZE)]
        for chunk in chunks:
            user_ad_profile_relation_dict = get_relation_dict(to_primary_key_name=config.AD_PROFILE_PRIMARY_KEY,
                                                              to_labels=config.AD_PROFILE_LABELS,
                                                              from_labels=config.PERSON_LABELS,
                                                              from_primary_key_name=config.PERSON_PRIMARY_KEY,
                                                              relationship_type=config.PERSON_AD_PROFILE_RELATION,
                                                              data=chunk)
            send_to_queue(user_ad_profile_relation_dict, self.queue_url)

    @staticmethod
    def _get_milliseconds_since_epoch():
        return time.get_milliseconds_since_epoch()

    def _populate_user_nodes(self):
        user_data = []
        for data in self.data_to_send:
            user_data.append(
                {
                    config.PERSON_PRIMARY_KEY: data[config.PERSON_PRIMARY_KEY],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    'created_at': data['created_at'],
                    'data_source': config.DATA_SOURCE
                })
        chunks = [user_data[i:i + config.QUEUE_CHUNK_SIZE] for i in range(0, len(user_data), config.QUEUE_CHUNK_SIZE)]
        for chunk in chunks:
            user_node_dict = get_node_dict(labels=config.PERSON_LABELS,
                                           primary_key_name=config.PERSON_PRIMARY_KEY,
                                           data=chunk)
            send_to_queue(user_node_dict, self.queue_url)

    def _populate_ad_profile_nodes(self):
        chunks = [self.data_to_send[i:i + config.QUEUE_CHUNK_SIZE] for i in range(0, len(self.data_to_send), config.QUEUE_CHUNK_SIZE)]
        for chunk in chunks:
            ad_node_dict = get_node_dict(labels=config.AD_PROFILE_LABELS,
                                         primary_key_name=config.AD_PROFILE_PRIMARY_KEY,
                                         data=chunk)

            send_to_queue(ad_node_dict, self.queue_url)

    def _update_company_ad_last_fetch_time(self):
        time_now = time_now_in_ad_format()
        data = [{config.AD_INSTANCE_PRIMARY_KEY: self.ad_url,
                 config.AD_INSTANCE_LAST_FETCH_TIME: time_now,
                 'dataSource': 'AD'}]
        channels_node_dict = get_node_dict(labels=config.AD_INSTANCE_LABELS,
                                           primary_key_name=config.AD_INSTANCE_PRIMARY_KEY,
                                           data=data)
        send_to_queue(channels_node_dict, self.queue_url)

    def _set_last_update_time_of_changed_fields(self):
        prev_ad_profiles = graph.get_ad_profiles(self.graph)

        # to search quickly if ad profile already exists
        prev_ad_profiles_email_map = {}
        for obj in prev_ad_profiles:
            prev_ad_profiles_email_map[obj[config.AD_PROFILE_PRIMARY_KEY]] = obj
        for data in self.data_to_send:
            if data[config.AD_PROFILE_PRIMARY_KEY] not in prev_ad_profiles_email_map:
                continue
            change_flag = False
            prev_ad_profile = prev_ad_profiles_email_map[data[config.AD_PROFILE_PRIMARY_KEY]]
            for key in self.keys_to_track:
                if data[key] != prev_ad_profile[key]:
                    change_flag = True
                else:
                    data[key + 'UpdateTime'] = prev_ad_profile[key + 'UpdateTime']
            if not change_flag:
                data['lastUpdateTime'] = prev_ad_profile['lastUpdateTime']

    def _populate_company_node(self):
        logger.info("Populating company node")
        company_node_dict = get_node_dict(labels=config.COMPANY_LABELS,
                                          primary_key_name=config.COMPANY_PRIMARY_KEY,
                                          data=[{
                                              config.COMPANY_PRIMARY_KEY: self.group_id,
                                              'data_source': config.DATA_SOURCE
                                          }])
        send_to_queue(company_node_dict, self.queue_url)

    def _populate_user_company_relations(self):
        user_company_relation_data = []
        for data in self.data_to_send:
            user_company_relation_data.append(
                get_relation_data_dict(to_key_value=self.group_id,
                                       from_key_value=data[config.PERSON_PRIMARY_KEY],
                                       properties={
                                        'performed_at': data['created_at'],
                                        'data_source': config.DATA_SOURCE
                                       }))
        chunks = [user_company_relation_data[i:i + config.QUEUE_CHUNK_SIZE] for i in
                  range(0, len(user_company_relation_data), config.QUEUE_CHUNK_SIZE)]
        for chunk in chunks:
            user_company_relation_dict = get_relation_dict(to_primary_key_name=config.COMPANY_PRIMARY_KEY,
                                                           to_labels=config.COMPANY_LABELS,
                                                           from_labels=config.PERSON_LABELS,
                                                           from_primary_key_name=config.PERSON_PRIMARY_KEY,
                                                           relationship_type=config.PERSON_COMPANY_RELATION,
                                                           data=chunk)
            send_to_queue(user_company_relation_dict, self.queue_url)

    def run(self):
        """
        Fetch (updated) AD data for one company
            If email already exists - update entry and add group that fetched the entry if not added
            If email does not exist - add entry and add group that fetched the entry
        """
        self._get_ldap_data()

        self._set_last_update_time_of_changed_fields()

        self._populate_ad_profile_nodes()
        logger.info('Checkpoint: Done populating ad profile nodes')

        self._populate_user_nodes()
        logger.info('Checkpoint: Done populating user nodes')

        self._populate_company_node()
        logger.info('Checkpoint: Done populating company node')

        self._populate_user_company_relations()
        logger.info('Checkpoint: Done populating user company relations')

        self._populate_user_ad_profile_relations()
        logger.info('Checkpoint: Done populating user-adProfile relations')

        self._update_company_ad_last_fetch_time()
        logger.info('Checkpoint: Done updating ad last-fetch-time')
