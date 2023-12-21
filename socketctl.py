from flask_socketio import SocketIO, send, emit
from classes.ocr import OCRObserver
from classes.data import VideoDataset
from classes.internet import get_remote_video_data
from classes.timeformula import minutes_difference
from datetime import datetime, timezone

import bg_celery.tasks as celery_task
import threading
import os
import json
import multiprocessing
import concurrent
import tempfile





def create_video_socket(app):
    _is_debug_mode = app.config['DEBUG']
    remote_video_url = app.config['VIDEO']['URL']
    
    remote_videos_data = get_remote_video_data(remote_video_url, _is_debug_mode)
    
    video_data = VideoDataset(remote_videos_data, debug_mode=_is_debug_mode)
    sio = VideoSocketIO(app, video_data)
    
    
    @sio.event
    def connect():
        app.logger.info('has a user connected.')

    @sio.event
    def disconnect():
        app.logger.info('a user disconnected.')

    @sio.on('message')
    def handle_message(data):
        app.logger.info('received message: {}'.format(data))
        if data == 'getinfo':
            emit('video_info', video_data.get_construct_info())
            emit('history_update', video_data.grab_history_warning())
        if data == 'reload':
            remote_videos_data = get_remote_video_data(remote_video_url, app, _is_debug_mode)
            video_data.load_data_from_url_videos(remote_videos_data)
            # video_data = VideoDataset(remote_videos_data, debug_mode=_is_debug_mode)
            sio.reload_video_data()
            emit('video_info', video_data.get_construct_info())
            emit('history_update', video_data.grab_history_warning())
            

    sio.start_background_ocrtask()

    return sio





class VideoSocketIO(SocketIO):
    """
    """
    flask_app = None
    ocr_observer = None
    data_ctl = None
    evt_exit_background = threading.Event()

    tmpdirname = ''



    def __init__(self, app, data_ctl: VideoDataset = None):
        super().__init__(app, async_mode='threading', cors_allowed_origins="*")
        # super().__init__(app, async_mode='eventlet', cors_allowed_origins="*")
        self.flask_app = app
        self.data_ctl = data_ctl
        self.ocr_observer = OCRObserver(app)
        app.logger.info(' [VideoSocketIO] Video Socket is Ready. Debug mode = {}'.format(app.config['DEBUG']))



    def exit_background_ocrtask(self):
        self.evt_exit_background.set()
        return self
    


    def start_background_ocrtask(self):
        self.start_background_task(self.background_multiprocess)
        return self
    


    def reload_video_data(self):

        # self.data_ctl.load_data_from_url_videos(url_videos)
        
        return self
    


    def background_multiprocess(self):
        TIMEOUT_CYCLE_CAPTURING = self.flask_app.config['HANDLER'].get('VIDEO_PROCESS_TIMEOUT', 60)

        with tempfile.TemporaryDirectory() as tmpdirname:
            self.flask_app.logger.info('Created Temporary Dicrectory : {}'.format(tmpdirname))
            self.tmpdirname = tmpdirname
            while not self.evt_exit_background.is_set():
                pid_urls = self.data_ctl.get_urls(is_activate=True)
                celery_frame_tasks = [celery_task.capture_video.delay(_['id'], _['url'], tmpdirname) for _ in pid_urls]

                self.while_working_by_celery_tasks(celery_frame_tasks, timeout=TIMEOUT_CYCLE_CAPTURING)

                for cft in celery_frame_tasks:
                    cft.revoke()

            self.tmpdirname = ''
        
        self.flask_app.logger.info('Background Task Stopped.')
        self.debug_logging()



    def while_working_by_celery_tasks(self, tasks:list, timeout:float=60):
        dt_start = datetime.utcnow()
        length_tasks = len(tasks)

        while not self.evt_exit_background.is_set():

            results = [task.get() for task in tasks if task.ready()]
            _len_results = len(results)
            if _len_results > 0:
                updated_ids = self.handle_video_frames()
                video_data_update_to_fronted = self.data_ctl.get_ws_video_data_by_ids(updated_ids)
                self.emit('video_data_update', video_data_update_to_fronted)
            else:
                self.evt_exit_background.wait(2)
            
            is_timeout = (datetime.utcnow() - dt_start).total_seconds() > timeout

            if _len_results >= length_tasks or is_timeout:
                not_open_ids = [res['pid'] for res in results if not res['opened']]
                self.flask_app.logger.info('Done A Cycle Capturing. Finished Length: {}'.format(length_tasks-len(not_open_ids)))

                self.data_ctl.set_error_with_not_open_videos(not_open_ids)
                video_data_update_to_fronted = self.data_ctl.get_ws_video_data_by_ids(not_open_ids)
                self.emit('video_data_update', video_data_update_to_fronted)
                break



    def handle_video_frames(self) -> list[str]:
        if not self.tmpdirname:
            return 
        
        ocr_obr = self.ocr_observer
        dt_now = datetime.utcnow()
        tmp_id_data = {}
        
        try:

            list_files_in_tmp = os.listdir(self.tmpdirname)

            for file in list_files_in_tmp:
                full_file_path = os.path.join(self.tmpdirname, file)
            
                [_id, _minute, _leftover] = file.split('_', 2)
                if minutes_difference(dt_now.minute, int(_minute)) < 2:

                    idata = tmp_id_data.get(_id, {'ontime': False, 'pubimg': False}) # ontime = find one on real time,  pubimg which is already saved a frame recently
                    if idata and idata['ontime']:
                        continue

                    image_frame, minute_parsed, other_images, digits = ocr_obr.get_parsed_frame_by_path(_id, full_file_path)
                    
                    idata['ontime'] = self.data_ctl.update_data_by_ocr_result(
                        id=_id,
                        minute=minute_parsed,
                        digits=digits,
                        yolo_images=other_images,
                        full_frame=image_frame
                    )

                    if idata['pubimg'] is False:
                        self.data_ctl.save_image(id=_id, img=image_frame)
                        idata['pubimg'] = True
                    
                    tmp_id_data[_id] = idata
                

                os.remove(full_file_path)
                
        except Exception as err:
            self.flask_app.logger.info(str(err))
        
        updated_ids = list(tmp_id_data.keys())
        spend_seconds = (datetime.utcnow() - dt_now).total_seconds()
        self.flask_app.logger.info('[handle_video_frames] spend secods: {},  total handle files: {}'.format(spend_seconds, len(list_files_in_tmp)))
        return updated_ids



    def debug_logging(self):
        logs = self.data_ctl.get_log_for_developer()
        accuracies = []
        for _k in logs:
            acc = logs[_k].get('accuracy', None)
            if acc is not None:
                print('{} : accuracy: {}'.format(_k, logs[_k]['accuracy']))
                accuracies.append(acc)
            else:
                print('{} : {}'.format(_k, logs[_k]))

        print('All Mean Accuracy: {}%'.format(round(sum(accuracies) *100 / len(accuracies))) )
        
        if self.flask_app.config['DEBUG']:
            with open(os.path.abspath(os.path.dirname(__file__)) + '/debug/debug_ocr.json', 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=4)

        





    