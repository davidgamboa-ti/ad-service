import time
import datetime


def get_milliseconds_since_epoch():
    return int(str(time.time()).split('.')[0] + '000')


def time_now_in_ad_format():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S.%fZ")

def timestamp_to_integer(time_stamp):
    try:
        return int(datetime.datetime.timestamp(time_stamp)*1000)
    except Exception as e:
        return ''