import requests
import json


local_url_videos = [
    {
        "vid": "D51",
        "flag": 1,
        "addr": "rtmp://live.bmez.cc/live/6-21.flv"
    },
    {
        "vid": "B01",
        "flag": 1,
        "addr": "rtmp://live.bmez.cc/tz01/8-11.flv"
    },
    {
        "vid": "N24",
        "flag": 1,
        "addr": "rtmp://live.bmez.cc/nw13/8-131.flv"
    },
    {
        "vid": "M52",
        "flag": 0,
        "addr": "rtmp://live.tgt14.com/mob/b1-21.flv"
    },
    {
        "vid": "B002",
        "flag": 1,
        "addr": "rtmp://live.youxiuzaoxing.xyz/tz01/8-21.flv"
    },
    {
        "vid": "D024",
        "flag": 1,
        "addr": "rtmp://live.youxiuzaoxing.xyz/live/7-11.flv"
    },
    {
        "vid": "N016",
        "flag": 0,
        "addr": "rtmp://N016"
    },
]


def retry_request(url:str, max:int = 3, is_json:bool = True) -> any:
    """ http request which can auto retry

    :url : url for http request
    :max : max times for retry
    :is_json: where parse response to json

    return json like dict object
    """
    _times = 0
    result = None
    while True:
        _times += 1
        try:
            response = requests.get(url)
            result = response.text
            if is_json:
                result = json.loads(result)

            break
        except requests.exceptions.ConnectionError as err:
            print(err)
        finally:
            if _times >= max:
                break
    
    return result



def get_remote_video_data(url:str, _is_debug_mode:bool = False) -> list:
    """ get videos datainfo by http request
    
    return [
        {
            vid: str ( a unique key for a video ),
            flag: int ( a number between 0-1 ),
            addr: str ( a url of rmpt ),
        },..
    ]
    """
    json_response = retry_request(url, max = 1 if _is_debug_mode else 3)
    vdatas = []
    if json_response is None:
        _remote_exception = 'Retry Request url:[ {} ] Is Failed.  Nothing Can Do.'.format(url)
        print(_remote_exception)
        raise Exception(_remote_exception)

    if isinstance(json_response, list) and len(json_response) > 0 and "vid" in json_response[0]:
        vdatas = json_response
    elif _is_debug_mode:
        vdatas = local_url_videos

    return vdatas