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
# import multiprocessing
# import concurrent
import tempfile
import tracemalloc
import linecache





def create_video_socket(app):
    _is_debug_mode = app.config['DEBUG']
    remote_video_url = app.config['VIDEO']['URL']
    remote_videos_data = get_remote_video_data(remote_video_url, _is_debug_mode)

    if _is_debug_mode:
        tracemalloc.start()
    
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
            sio.reload_tasks()
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
    evt_video_handling = threading.Event()

    tmp_hourly_refresh = 0
    celery_frame_tasks = []



    def __init__(self, app, data_ctl: VideoDataset = None):
        super().__init__(app, async_mode='threading', cors_allowed_origins="*", allow_unsafe_werkzeug=True)
        # super().__init__(app, async_mode='eventlet', cors_allowed_origins="*")
        self.flask_app = app
        self.data_ctl = data_ctl
        self.ocr_observer = OCRObserver(app)
        app.logger.info(' [VideoSocketIO] Video Socket is Ready. Debug mode = {}'.format(app.config['DEBUG']))



    def exit_background_ocrtask(self):
        self.evt_exit_background.set()
        self.evt_video_handling.set()
        return self
    


    def start_background_ocrtask(self):
        self.start_background_task(self.background_multiprocess)
        return self
    


    def reload_video_data(self):
        remote_videos_data = get_remote_video_data(self.flask_app.config['VIDEO']['URL'])
        self.data_ctl.load_data_from_url_videos(remote_videos_data)
        return self
    


    def reload_tasks(self):
        self.evt_video_handling.set()
        for cft in self.celery_frame_tasks:
            cft.revoke()
        celery_task.app.control.purge()
        self.celery_frame_tasks = []


    
    def check_video_status_hourly(self):
        dt_now = datetime.utcnow()
        if dt_now.hour != self.tmp_hourly_refresh:
            self.tmp_hourly_refresh = dt_now.hour
            remote_videos_data = get_remote_video_data(self.flask_app.config['VIDEO']['URL'])
            self.data_ctl.refresh_data_from_url_videos(remote_videos_data)



    def background_multiprocess(self):
        TIMEOUT_CYCLE_CAPTURING = self.flask_app.config['HANDLER'].get('VIDEO_PROCESS_TIMEOUT', 60)

        with tempfile.TemporaryDirectory() as tmpdirname:
            self.flask_app.logger.info('Created Temporary Dicrectory : {}'.format(tmpdirname))
            # self.tmpdirname = tmpdirname
            while not self.evt_exit_background.is_set():
                pid_urls = self.data_ctl.get_urls(is_activate=True)
                self.celery_frame_tasks = [celery_task.capture_video.delay(_['id'], _['url']) for _ in pid_urls]
                self.evt_video_handling = threading.Event()
                self.while_working_by_celery_tasks(timeout=TIMEOUT_CYCLE_CAPTURING)
                self.reload_tasks()
                self.check_video_status_hourly()
                # 
                
                if self.flask_app.config['DEBUG']:
                    snapshot = tracemalloc.take_snapshot()
                    self.debug_display_memo_top(snapshot)

            # self.tmpdirname = ''
        
        self.flask_app.logger.info('Background Task Stopped.')
        self.debug_logging()



    def while_working_by_celery_tasks(self, timeout:float=60):
        dt_start = datetime.utcnow()
        self.next_round_done_video_id_map = {}
        
        while not self.evt_exit_background.is_set():
            tasks = self.celery_frame_tasks
            length_tasks = len(tasks)

            results = [task.get() for task in tasks if task.ready()]
            _len_results = len(results)
            if _len_results > 0:
                new_results = [_ for _ in results if self.next_round_done_video_id_map.get(_['pid'], None) is None and _['opened']]
                updated_ids = self.handle_video_tasks(new_results) # it will take a long time to execute
                if len(updated_ids) == 0:
                    self.evt_exit_background.wait(2)
                else:
                    for _pid in updated_ids:
                        self.next_round_done_video_id_map[_pid] = True
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



    def handle_video_tasks(self, task_results:list=[]) -> list[str]:
        # MAX_HANDLE_FRAME = 50
        dt_now = datetime.utcnow()
        num_done_frame = 0
        updated_ids = []
        
        try:
            for task_res in task_results:
                if self.evt_video_handling.is_set():
                    break
                pid = task_res['pid']
                task_minute = task_res['minute']
                task_frames = task_res['frames']
                if minutes_difference(dt_now.minute, int(task_minute)) < 2:

                    parsed_minutes = self.handle_frames(pid, task_frames)
                    num_done_frame += len(parsed_minutes)
                    updated_ids.append(pid)
                
        except Exception as err:
            self.flask_app.logger.info(str(err))
            # self.reload_tasks()
            # self.exit_background_ocrtask()
        
        spend_seconds = (datetime.utcnow() - dt_now).total_seconds()
        self.flask_app.logger.info('[handle_video_tasks] spend secods: {},  total handle files: {}  updated ids: {}'.format(spend_seconds, num_done_frame, len(updated_ids)))
        return updated_ids



    def handle_frames(self, pid:str, frames:list):
        result_minuts = []
        ocr_obr = self.ocr_observer
        _tmp_xyxy = []
        _depth_yolo = 0

        for frame in frames:

            if len(_tmp_xyxy) == 4:
                minute_parsed, digits = ocr_obr.get_parsed_digits_by_frame_and_position(frame, _tmp_xyxy)
                _depth_yolo = 2
            else:
                image_frame, minute_parsed, digits, yolo_find_images, xyxy_datetime = ocr_obr.get_parsed_frame(frame)
                _depth_yolo = len(yolo_find_images)
                _tmp_xyxy = xyxy_datetime

                self.data_ctl.save_image(id=pid, img=image_frame)
                
                # self.data_ctl.debug_logging(id=pid, full_frame=image_frame, minute=minute_parsed, yolo_images=yolo_find_images, digits=digits, depth_yolo=_depth_yolo)
            result_minuts.append(minute_parsed)

            is_ontime = self.data_ctl.update_data_by_ocr_result(
                id=pid,
                minute=minute_parsed,
                digits=digits,
                depth_yolo=_depth_yolo,
            )

            if is_ontime:
                break

        return result_minuts



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
        
        if len(accuracies) > 0:
            print('All Mean Accuracy: {}%'.format(round(sum(accuracies) *100 / len(accuracies))) )
        
        if self.flask_app.config['DEBUG']:
            with open(os.path.abspath(os.path.dirname(__file__)) + '/debug/debug_ocr.json', 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=4)



    def debug_display_memo_top(self, snapshot, key_type='lineno', limit=10):
        print(" [ TOP Memory Stats ] ")
        snapshot = snapshot.filter_traces((
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        ))
        top_stats = snapshot.statistics(key_type)

        print(" -- Show Top {} lines".format(limit))
        for index, stat in enumerate(top_stats[:limit], 1):
            frame = stat.traceback[0]
            print("#{}: {}:{}:  size: {:.1f} KiB".format(index, frame.filename, frame.lineno, stat.size / 1024))
            line = linecache.getline(frame.filename, frame.lineno).strip()
            if line:
                print('    ', line)

        other = top_stats[limit:]
        if other:
            size = sum(stat.size for stat in other)
            print("other length: {}  |  other size: {:.1f} KiB".format(len(other), size / 1024))
        total = sum(stat.size for stat in top_stats)
        print("Total allocated size: {:.1f} KiB".format(total / 1024))

        





    