from celery import Celery
from datetime import datetime
import cv2
import json
import os

os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

app = Celery('tasks')
app.conf.update(
    broker_url = 'redis://localhost:6379/0',
    result_backend = 'redis://localhost:6379/0',
    result_serializer = 'json',
    accept_content = ['application/json'],
    enable_utc = True,
    result_expires = 30,
    # task_reject_on_worker_lost = True,
)



@app.task
def capture_video(pid: str, rtmp_url: str, dir_location: str) -> dict[str, any]:
    """Async task to capture frame from rtmp url 

    :pid : a unique key name for live streaming room
    :rtmp_url : a url used by cv2.VideoCapture to catch live streaming frames
    :dir_location : an absolute system file path where temporary file has saved

    Return:
    {
        pid: String,
        opened: Boolean,
        frames: String[],
    }
    """

    SECOND_INTERVAL = 1
    MAX_FRAME_LENGTH = 3
    length_frame = 0
    last_dt = datetime.utcnow()
    result = {'pid': pid, 'opened': True, 'frames': []}

    if not os.path.isdir(dir_location):
        raise Exception('Not Found Directory: {}. '.format(dir_location))

    cap = cv2.VideoCapture(rtmp_url)
    
    if not cap.isOpened():
        result['opened'] = False
        return result
    

    while length_frame < MAX_FRAME_LENGTH:
        ret, frame = cap.read()
        now = datetime.utcnow()
        if (now - last_dt).total_seconds() < SECOND_INTERVAL:
            continue
        
        if ret:

            last_dt = now
            jpg_name = '{}_{}_{}.jpg'.format(pid, now.minute, now.second)
            full_path = os.path.join(dir_location, jpg_name)
            cv2.imwrite(full_path, frame)
            result['frames'].append(str(full_path))
            length_frame += 1
        else:
            break
    
    return result



    