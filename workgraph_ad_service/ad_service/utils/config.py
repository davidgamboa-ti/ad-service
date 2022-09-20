import logging
from iws_logging import get_logger

from workgraph_ad_service.settings import DEBUG

if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
    LOGGER = logging
else:
    LOGGER = get_logger("ad_integration_dev_logger", allow_docker_construct=False)

# keys for fields fetched from active directory -- https://msdn.microsoft.com/en-us/library/ms677980.aspx
AD_TITLE = 'title'
AD_USERNAME = 'sAMAccountName'
AD_PRINCIPAL_NAME = 'userPrincipalName'
AD_GUID = 'objectGUID'
AD_COMPANY = 'company'
AD_PHONE_NUMBER = 'mobile'
AD_PERSONAL_WEBSITE = 'wWWHomePage'
AD_COUNTRY = 'co'
AD_CITY = 'L'
AD_DISTINGUISHED_NAME = 'distinguishedName'
AD_EMAIL = 'mail'
AD_FIRST_NAME = 'givenName'
AD_LAST_NAME = 'sn'
AD_NAME = 'name'
AD_DIVISION = 'division'
AD_DEPARTMENT = 'department'
AD_MANAGER = 'manager'
AD_DIRECT_REPORTS = 'directReports'
AD_MEMBER_OF = 'memberOf'
AD_WHEN_CREATED = 'whenCreated'
DATA_SOURCE = 'active_directory'

# ad search filter to get non-disabled users
AD_SEARCH_FILTER = '(&(objectCategory=person)(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'

PAGINATION_SIZE = 1000  # max limit is 1000

# graph schema constants
AD_PROFILE_LABELS = ['Profile', 'ADProfile']
AD_PROFILE_PRIMARY_KEY = 'primary_email'

COMPANY_LABELS = ['Company']
COMPANY_PRIMARY_KEY = 'company_id'
PERSON_COMPANY_RELATION = 'belongs_to'

AD_INSTANCE_LABELS = ['ADInstance']
AD_INSTANCE_PRIMARY_KEY = 'instance_url'
AD_INSTANCE_LAST_FETCH_TIME = 'last_fetch_time'

PERSON_LABELS = ['Person']
PERSON_PRIMARY_KEY = 'primary_email'
PERSON_CREATE_TIME = 'create_time'

PERSON_AD_PROFILE_RELATION = 'has_profile'

INDEX_LABEL_PROPERTY_MAP = {
    'Person': 'primaryEmail',
    'ADProfile': 'primaryEmail',
}

#GRAPH_BOLT = False
GRAPH_BOLT = True

# test graph
TEST_GRAPH_URL = 'http://neo4j:12345@webserver.devfactory.com:10048/'
TEST_QUEUE_URL = 'http://webserver.devfactory.com:10054/queue/'
TEST_GRAPH_BOLT = False

# retry params while connecting to queue
QUEUE_MAX_RETRIES = 5
QUEUE_RETRY_TIME = 5000

# list size to send to queue to batch populate
QUEUE_CHUNK_SIZE = 800

ADMIN_PORTAL_URL = "http://workgraph-admin-portal-backend-dev.public.ey.devfactory.com"

