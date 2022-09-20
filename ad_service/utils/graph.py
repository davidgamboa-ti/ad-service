import ad_service.utils.config as constants


def get_ad_profiles(graph):
    query = "match (n:ADProfile) return n"
    users = []
    for record in graph.run(query):
        users.append(record.get('n'))
    return users


def get_ldap_last_fetch_time(graph, ldap_url):
    query = "match (n:{0} {{instanceUrl: \"{1}\"}}) return n.{2}".format(constants.AD_INSTANCE_LABELS[0], ldap_url,
                                                                         constants.AD_INSTANCE_LAST_FETCH_TIME)
    last_fetch_time = None
    for record in graph.run(query):
        last_fetch_time = record[0]
    return last_fetch_time
