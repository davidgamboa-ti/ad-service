import json
from django.http import HttpResponse
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError
from rest_framework.decorators import api_view
from ad_service.ad_integration.onboard_and_update import ADIntegration
from ad_service.utils import config
from ad_service.utils.queue import *
from ad_service.utils.security import *

logger = config.LOGGER


def response_handler(*args, **kwargs):
    return HttpResponse(json.dumps(kwargs), status=args[0], content_type="application/json")


def send_confirmation(queue_url, state, is_success, reason=None):
    confirmation_dict = get_confirmation_dict(state, is_success, reason)
    send_to_queue(confirmation_dict, queue_url)
    logger.info('Checkpoint: Sent confirmation. state: {0} is_success: {1} reason: {2}'.format(state, is_success, reason))


@api_view(['GET'])
def health(request):
    logger.info("health check")
    return response_handler(200, text='v1')


@api_view(['POST'])
def check_credentials(request):
    logger.info("got check credentials request")
    try:
        ad_url = request.data['ldap_url']
        ad_password = request.data['ldap_password']
        ad_username = request.data['ldap_username']
        ad_search_base = request.data['ldap_search_base']
        integration_id = request.data['integration_id']
        state = request.data['state']
    except KeyError as e:
        logger.exception(repr(e))
        return response_handler(400, is_success= False, reason='Missing Fields!')

    logger.info("no keyerror")
    try:
        logger.info('Checking LDAP credentials')
        server = Server(ad_url, get_info=ALL)
        conn = Connection(server, ad_username, ad_password, auto_bind=True)
    except (LDAPBindError, LDAPSocketOpenError) as e:
        logger.exception('Invalid LDAP credentials ' + ad_url + " " + repr(e))
        return response_handler(400, is_success = False, reason = 'Invalid LDAP credentials')
    except Exception as e:
        logger.exception("Exp: Invalid LDAP credentials " + repr(e))
        return response_handler(400, is_success = False, reason = 'Invalid LDAP credentials')

    logger.info("credentials good, posting credentials to admin portal")
    return response_handler(200, is_success = True, reason = 'Valid Credentials')
    # we are here means credentials are valid
    # set credentials in database by posting it to Admin Portal
    # response = requests.post(
    #     "{admin_portal_url}/api/groups/{state}/integrations/{integration_id}/onboard_integration/"
    #     .format(admin_portal_url=config.ADMIN_PORTAL_URL,
    #             state=state,
    #             integration_id=integration_id),
    #     json={
    #         "ldap_url": request.data['ldap_url'],
    #         "ldap_password": request.data['ldap_password'],
    #         "ldap_username": request.data['ldap_username'],
    #         "ldap_search_base": request.data['ldap_search_base'],
    #     })
    # admin_portal_response = json.loads(response.text)
    # logger.info("post response " + str(response.status_code) + " " + str(response.content))
    # return response_handler(200, is_success = admin_portal_response['is_success'], reason = admin_portal_response['reason'])


@api_view(['POST'])
def ad_integration(request):
    logger.info('got onboarding request')
    try:
        ad_url = request.data['ldap_url']
        ad_password = request.data['ldap_password']
        ad_username = request.data['ldap_username']
        ad_search_base = request.data['ldap_search_base']
        graph_url = request.data['graph_url']
        queue_url = request.data['queue_url']
        group_id = request.data['group_id']
        state = request.data['state']
    except KeyError as e:
        logger.exception(repr(e))
        return response_handler(400, status='failure', reason='Missing Fields!')

    logger.info('no keyerror')
    try:
        logger.info('Checkpoint: Indexing labels ...')
        for label in config.INDEX_LABEL_PROPERTY_MAP:
            index_dict = get_index_dict(label=label, property=config.INDEX_LABEL_PROPERTY_MAP[label])
            send_to_queue(index_dict, queue_url)
        logger.info('Checkpoint: Indexed labels! Starting integration ...')
        ADIntegration(ad_url, ad_username, ad_password, ad_search_base, graph_url, queue_url, group_id).run()
    except (LDAPBindError, LDAPSocketOpenError):
        logger.exception('Invalid LDAP credentials ' + ad_url)
        send_confirmation(queue_url=queue_url, state=state, is_success=False, reason='Invalid LDAP credentials!')
        return response_handler(400)
    except Exception as e:
        logger.exception('sent confirmation to queue success=False ' + repr(e))
        send_confirmation(queue_url=queue_url, state=state, is_success=False,
                          reason='Internal Server Error! Please try again!')
        return response_handler(400)

    send_confirmation(queue_url=queue_url, state=state, is_success=True)
    logger.info('sent confirmation to queue success=True')
    return response_handler(200)
