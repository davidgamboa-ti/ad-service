import requests
from retrying import retry
import ad_service.utils.config as constants

logger = constants.LOGGER


def get_confirmation_dict(state, is_success, reason=None):
    confirmation_dict = {
        "type": "CONFIRM",
        "event_data": {
            "state": state,
            "is_success": is_success
        }
    }
    if reason:
        confirmation_dict["event_data"]["reason"] = reason
    return confirmation_dict


def get_index_dict(label, property):
    index_dict = {
        "type": "INDEX",
        "event_data": {
            "label": label,
            "property": property,
        }
    }
    return index_dict


def get_relation_data_dict(to_key_value, from_key_value, properties):
    data = {
        "node_from_primary_key_value": from_key_value,
        "node_to_primary_key_value": to_key_value,
        "properties": properties
    }
    return data


def get_relation_update_dict(from_labels, from_primary_key_name, to_labels, to_primary_key_name, property_names, data,
                             relationship_type, property_type="INT"):
    return {
        "type": "RELATIONSHIP_VALUE_ADD",
        "event_data": {
            "from": {
                "labels": from_labels,
                "primary_key_name": from_primary_key_name
            },
            "to": {
                "labels": to_labels,
                "primary_key_name": to_primary_key_name
            },
            "type": relationship_type,
            "property_names": property_names,
            "property_type": property_type,
            "data": data
        }
    }


def get_node_dict(labels, primary_key_name, data):
    node_dict = {
        "type": "NODE",
        "event_data": {
            "labels": labels,
            "primary_key_name": primary_key_name,
            "data": data
        }
    }
    return node_dict


def get_relation_dict(to_primary_key_name, to_labels, from_labels, from_primary_key_name, relationship_type, data,
                      edge_primary_key_name=None):
    relation_dict = {
        "type": "RELATIONSHIP",
        "event_data": {
            "from": {
                "labels": from_labels,
                "primary_key_name": from_primary_key_name
            },
            "to": {
                "labels": to_labels,
                "primary_key_name": to_primary_key_name
            },
            "type": relationship_type,
            "data": data
        }
    }
    if edge_primary_key_name is not None:
        relation_dict["primary_key_name"] = edge_primary_key_name
    return relation_dict


@retry(stop_max_attempt_number=constants.QUEUE_MAX_RETRIES, wait_fixed=constants.QUEUE_RETRY_TIME)
def send_to_queue(data_to_send, queue_url):
    if data_to_send['type'] not in ['INDEX', 'CONFIRM'] and len(data_to_send['event_data']['data']) == 0:
        logger.info('Nothing to populate. Moving on..')
        return
    r = requests.post(queue_url, json=data_to_send)
    if r.status_code != 200:
        logger.info('Unable to populate into queue! Retrying after {0} sec'.format(constants.QUEUE_RETRY_TIME / 1000))
        raise RuntimeError('Unable to populate into queue')
    else:
        logger.info('Populate successful!')
