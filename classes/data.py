from PIL import Image
from datetime import datetime
from classes.timeformula import check_minute_normally
from enum import Enum
import os
import cv2
import json




class VideoFlagENum(Enum):
    CLOSE = 0
    OPEN = 1
    PEDDING = 2
    ERROR = 4




class VideoProcessStatusEnum(Enum):
    PREPARING = 0
    NO_PANEL = 1
    NO_DATETIME = 2
    WRONG_FORMAT = 3
    MINUTE_FOUND = 4




class VideoDataset():
    """ store all datainfo of videos. 

    init parameter must be like [
        {
            vid: str,
            flag: int,
            addr: str,
        },
    ]
    """
    STR_DEBUG_LOG_HISTORY = '_debug_history'
    construct_videos = []
    map_video_index = {}
    current_path = os.path.abspath(os.path.dirname(__file__))
    debug_mode = False
    list_history_warning = []

    log_dev = {}



    def __init__(self, url_videos:list, debug_mode:bool = False) -> None:
        self.debug_mode = debug_mode
        if debug_mode:
            self.log_dev[self.STR_DEBUG_LOG_HISTORY] = {}
        self.load_data_from_url_videos(url_videos)



    def load_data_from_url_videos(self, url_videos:list):
        videos = []
        dict_map = {}
        for _vdata in url_videos:
            _vid = _vdata.get('vid', None)
            _addr = _vdata.get('addr', None)
            _flag = _vdata.get('flag', VideoFlagENum.CLOSE)
            if _vid is None or _addr is None:
                print('[VideoDataset] parsing failed. data: ', _vdata)
                continue

            dict_map[_vid] = len(videos)
            videos.append({
                'id': _vid,
                'img': '/public/{}.jpg'.format(_vid),
                'flag': VideoFlagENum(_flag),
                # 'ontime': True,
                'minute_last': -1,
                'minute_flexible': -1,
                'list_past_minutes': [],
                'last_timestamp': '',
                'url': _addr,
                'wrongs': {
                    'datetime': 0,
                    'format': 0,
                    'overtime': 0,
                },
                'warning': {
                    'datetime': False,
                    'format': False,
                    'overtime': False,
                },
                'parsed_digits': []
            })

        self.construct_videos = videos
        self.map_video_index = dict_map
        self.list_history_warning = []



    def refresh_data_from_url_videos(self, url_videos:list):
        videos = self.construct_videos
        map_vidx = self.map_video_index
        for _vdata in url_videos:
            _vid = _vdata.get('vid', None)
            _addr = _vdata.get('addr', None)
            _flag = _vdata.get('flag', VideoFlagENum.CLOSE)
            if _vid is None or _addr is None:
                continue
            idx = map_vidx.get(_vid, -1)
            if idx >= 0 and idx < len(videos):
                videos[idx]['url'] = _addr
                videos[idx]['flag'] = VideoFlagENum(_flag)




    def get_construct_info(self) -> list[dict]:
        return [self.get_dict_by_keys(_, ['id', 'img', 'flag', 'wrongs', 'warning']) for _ in self.construct_videos]
    


    def get_urls(self, is_activate:bool = True) -> list[dict]:
        """ get dict[id, url, flag] all videos, if parameter is_activated is True then filter only opened video
        """
        if is_activate:
            return [self.get_dict_by_keys(_, ['id', 'url', 'flag']) for _ in self.construct_videos if _['flag'] == VideoFlagENum.OPEN]
        else:
            return [self.get_dict_by_keys(_, ['id', 'url', 'flag']) for _ in self.construct_videos]
    


    def get_dict_by_keys(self, obj:dict, keys:list = []) -> dict:
        result = {}
        for k in keys:
            result[k] = obj.get(k, None)
            if k == 'flag' and isinstance(result[k], VideoFlagENum):
                result[k] = int(result[k].value)
        
        return result
    


    def get_video_construct_pointer_by_id(self, id:str):
        idx = self.map_video_index.get(id, -1)
        if idx == -1:
            return {}
        
        return self.construct_videos[idx]
    


    def get_ws_video_data_by_ids(self, ids:list):
        vdata = [
            self.get_dict_by_keys(
                self.get_video_construct_pointer_by_id(id),
                ['id', 'flag', 'minute_flexible', 'minute_last', 'last_timestamp','wrongs', 'warning', 'parsed_digits']
            )
        for id in ids]
        
        return vdata
    


    def tape_video_fail_by_id(self, id:str):
        pointer = self.get_video_construct_pointer_by_id(id)
        pointer['flag'] = VideoFlagENum.ERROR
        return pointer
    


    def get_process_status(self, minute:int, depth_yolo:int) -> VideoProcessStatusEnum:
        dt_now = datetime.utcnow()
        if depth_yolo == 0:
            return VideoProcessStatusEnum.NO_PANEL
        elif depth_yolo == 1:
            return VideoProcessStatusEnum.NO_DATETIME
        elif check_minute_normally(minute, dt_now.minute):
            return VideoProcessStatusEnum.MINUTE_FOUND
        else:
            return VideoProcessStatusEnum.WRONG_FORMAT
        


    def update_data_by_ocr_result(self, id:str, minute:int, digits:list[str], depth_yolo:int) -> bool:
        """ update processed data into data center
        
        """
        pointer = self.get_video_construct_pointer_by_id(id)
        dt_now = datetime.utcnow()
        ontime = False

        pointer['minute_last'] = minute
        pointer['parsed_digits'] = digits
        pointer['last_timestamp'] = dt_now.strftime("%Y-%m-%d %H:%M:%S")

        process_status = self.get_process_status(minute, depth_yolo)

        if process_status is VideoProcessStatusEnum.NO_PANEL or process_status is VideoProcessStatusEnum.NO_DATETIME:
            pointer['wrongs']['datetime'] += 1

        elif process_status is VideoProcessStatusEnum.WRONG_FORMAT:
            if pointer['warning']['format']:
                pointer['wrongs']['format'] = 0
            pointer['wrongs']['format'] += 1
            # pointer['minute_flexible'] = minute # trans by some algo
        
        elif process_status is VideoProcessStatusEnum.MINUTE_FOUND:
            pointer['wrongs']['format'] = 0
            pointer['wrongs']['datetime'] = 0

            pointer['minute_flexible'] = minute
            ontime = self.check_minute_ontime(pointer['minute_flexible'], dt_now.minute)
            if ontime:
                pointer['wrongs']['overtime'] = 0
            else:
                pointer['wrongs']['overtime'] += 1
        

        pointer['warning']['overtime'] = pointer['wrongs']['overtime'] > 2
        pointer['warning']['datetime'] = pointer['wrongs']['datetime'] > 4
        pointer['warning']['format'] = pointer['wrongs']['format'] > 6
        

        self.refresh_history_by_video_construct(pointer)

        self.stamp_analyzing(id=id, process_status=process_status, ontime=ontime)
        
        return ontime
    


    def debug_logging(self, id:str, full_frame:any, minute:int, yolo_images:list, digits:list, depth_yolo:int):
        if self.debug_mode:
            self.logging_while_update_video_data(
                id=id,
                process_status=self.get_process_status(minute, depth_yolo), 
                image=full_frame,
                yolo_images=yolo_images,
                digits=digits
            )



    def refresh_history_by_video_construct(self, vc_data:dict) -> None:
        for _wkey in vc_data['warning']:
            if vc_data['warning'][_wkey]:
                self.list_history_warning.append({
                    'id': vc_data['id'],
                    'key': _wkey,
                    'flexible': vc_data['minute_flexible'],
                    'digits': vc_data['parsed_digits'],
                    'time': vc_data['last_timestamp']
                })
        
        if len(self.list_history_warning) > 50:
            self.list_history_warning = self.list_history_warning[-50:]
    


    def grab_history_warning(self, get_newest:bool=False) -> list[dict]:
        if get_newest:
            now = datetime.now()
            warning_results = [_ for _ in self.list_history_warning if _['time'] >= now]
            return warning_results

        return self.list_history_warning



    def save_image(self, id:str, img:any, specify_path:str = ''):
        path = ''
        # _next_img = Image.fromarray(img.astype('uint8'), mode='RGB')
        # if resize != 1 and resize > 0:
        #     _shape = [_ // resize for _ in img.shape[:2]]
        #     _next_img.thumbnail(_shape)
        
        if specify_path:
            if '{}' in specify_path:
                path = os.path.join(self.current_path, '..', specify_path.format(id, datetime.now().strftime('%H%M')))
            else:
                path = os.path.join(self.current_path, '..', specify_path)
        else:
            path = os.path.join(self.current_path, '..', 'public', '{}.jpg'.format(id))

        # _next_img.save(path, 'JPEG')
        cv2.imwrite(path, img)
        
        return path
    


    def check_minute_ontime(self, minute: int, now: int) -> bool:
        if minute == now:
            return True
        if now == 0:
            return minute == 59
        return abs(now - minute) < 2
    


    def find_most_common(self, lst):
        _dict = {}
        _closely = 6
        for _ in lst:
            if _ in _dict:
                _dict[_] += _closely
            else:
                _dict[_] = _closely
            _closely -= 1
        return max(_dict, key=_dict.get)
    


    def get_log_for_developer(self):

        return self.log_dev
    
    
    def stamp_analyzing(self, id:str, process_status:VideoProcessStatusEnum, ontime:bool):
        _analyzing_key = 'analyzing_{}'.format(id)
        if self.log_dev.get(_analyzing_key, None) is None:
            self.log_dev[_analyzing_key] = {'total': 0, 'right': 0, 'no_panel': 0, 'no_datetime': 0, 'wrong_format': 0, 'wrong_time': 0, 'accuracy': 0.0}
        _ana_pointer = self.log_dev[_analyzing_key]
        _ana_pointer['total'] += 1

        if process_status is VideoProcessStatusEnum.MINUTE_FOUND:
            if ontime:
                _ana_pointer['right'] += 1
            else:
                _ana_pointer['wrong_time'] += 1

        elif process_status is VideoProcessStatusEnum.NO_PANEL:
            _ana_pointer['no_panel'] += 1

        elif process_status is VideoProcessStatusEnum.NO_DATETIME:
            _ana_pointer['no_datetime'] += 1

        elif process_status is VideoProcessStatusEnum.WRONG_FORMAT:
            _ana_pointer['wrong_format'] += 1

        _ana_pointer['accuracy'] = _ana_pointer['right'] / _ana_pointer['total']



    def logging_while_update_video_data(self, id:str, process_status:VideoProcessStatusEnum, image:any, yolo_images:list[any], digits:list):
        if self.log_dev[self.STR_DEBUG_LOG_HISTORY].get(id, None) is None:
            self.log_dev[self.STR_DEBUG_LOG_HISTORY][id] = []

        _dev_pointer = self.log_dev[self.STR_DEBUG_LOG_HISTORY][id]


        if process_status is VideoProcessStatusEnum.NO_PANEL:
            self.save_image(id, image, specify_path='debug/no_panel_found_{}_{}.jpg')

        elif process_status is VideoProcessStatusEnum.NO_DATETIME:
            self.save_image(id, image, specify_path='debug/no_datetime_found_{}_{}.jpg')

        elif process_status is VideoProcessStatusEnum.WRONG_FORMAT:
            if self.get_video_construct_pointer_by_id(id)['warning']['format']:
                path_img = self.save_image(id, yolo_images[-1], specify_path='debug/wrong_format_{}_{}_img_datetime.jpg')
                _dev_pointer.append({
                    'digits': digits,
                    'ans_minute': datetime.now().minute,
                    'img_datetime': path_img,
                })



    def set_error_with_not_open_videos(self, ids = []):
        map_vi = self.map_video_index
        for _id in ids:
            _idx = map_vi.get(_id, -1)
            if _idx:
                self.construct_videos[_idx]['flag'] = VideoFlagENum.ERROR
    

    

        