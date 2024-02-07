from celery import Celery
from datetime import datetime
import cv2
import json
import pickle
import os
import numpy as np

os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')
os.environ.setdefault('CELERY_TASK_ACKS_LATE', 'True')
os.environ.setdefault('CELERY_BROKER_MAXMEMORY_POLICY', '"allkeys-lru')
os.environ.setdefault('CELERY_BROKER_MAXMEMORY', '2048M')
os.environ.setdefault('CELERY_WORKER_PREFETCH_MULTIPLIER', '1')
os.environ.setdefault('CELERYD_TASK_TIME_LIMIT', '60')

docker_network_alias = os.environ.get('REDIS_ALIAS', 'localhost')
# print('[Network] Redis Alias Name: ', docker_network_alias)

app = Celery('tasks')
app.conf.update(
    broker_url = 'redis://{}:6379/0'.format(docker_network_alias),
    result_backend = 'redis://{}:6379/0'.format(docker_network_alias),
    result_serializer = 'pickle',
    task_serializer = 'pickle',
    accept_content = ['application/json', 'pickle'],
    enable_utc = True,
    result_expires = 30,
    # task_reject_on_worker_lost = True,
)



@app.task
def capture_video(pid: str, rtmp_url: str, dir: str = '') -> dict[str, any]:
    """Async task to capture frame from rtmp url 

    :pid : a unique key name for live streaming room
    :rtmp_url : a url used by cv2.VideoCapture to catch live streaming frames

    Return:
    {
        pid: String,
        opened: Boolean,
        frames: String[],
        minute: Integer,
    }
    """

    SECOND_INTERVAL = 1
    MAX_FRAME_LENGTH = 3
    length_frame = 0
    last_dt = datetime.utcnow()
    result = {'pid': pid, 'opened': False, 'frames': [], 'minute': -1}
    _is_save_file = False
    if dir != '':
        _is_save_file = True
        path_save_file_dir = os.path.join(dir, 'tmp')
        if not os.path.isdir(path_save_file_dir):
            os.makedirs(path_save_file_dir, exist_ok=True)

    try:

        cap = cv2.VideoCapture(rtmp_url)
        
        if not cap.isOpened():
            return result

        while length_frame < MAX_FRAME_LENGTH:
            ret, frame = cap.read()
            now = datetime.utcnow()
            if (now - last_dt).total_seconds() < SECOND_INTERVAL:
                continue
            
            if ret:
                
                if _is_save_file:
                    file_name = '{}_{}.jpg'.format(pid, length_frame + 1)
                    path_saved_file = str(os.path.join(path_save_file_dir, file_name))
                    cv2.imwrite(path_saved_file, frame)
                    result['frames'].append(path_saved_file)
                else:
                    result['frames'].append(frame)

                result['minute'] = now.minute
                length_frame += 1
                last_dt = now
            else:
                break

        result['opened'] = True

    except cv2.error as e:
        print(e)
        del result['frames']
        result['frames'] = []
    
    return result



    