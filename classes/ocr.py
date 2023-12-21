from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any
from ultralytics import YOLO
from ultralytics.utils.plotting import Annotator


# import keras_ocr
import pytesseract
import cv2
import re
import threading
import multiprocessing
import os
import numpy as np
# import ffmpeg

# for parseq
import torch
from PIL import Image
from parseq.strhub.data.module import SceneTextDataModule
from classes.timeformula import minutes_difference



class OCRObserver():
    """
    
    """
    flask_app = None
    model_yolo_glance = None
    model_yolo_focus_on = None
    tesseract_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789:CGMT/+'
    num_cpus = 6
    # bound_rgbimg_lower = np.array([48,96,128])
    # bound_rgbimg_upper = np.array([212,244,255])

    parseq = None
    parseq_img_transform = None


    def __init__(self, flask_app) -> None:
        self.flask_app = flask_app
        self.load_yolo()
        self.setting_tesseract()
        self.load_parseq()

        self.logging(' * OCR Observer Loaded.')


    def load_yolo(self):
        if self.flask_app.config['YOLO']:
            if self.flask_app.config['YOLO']['GLANCE']:
                path_yolov8  = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'model', 'yolo', self.flask_app.config['YOLO']['GLANCE'])
                self.model_yolo_glance = YOLO(path_yolov8)
            if self.flask_app.config['YOLO']['FOCUSON']:
                path_yolov8  = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'model', 'yolo', self.flask_app.config['YOLO']['FOCUSON'])
                self.model_yolo_focus_on = YOLO(path_yolov8)
        else:
            raise Exception('Setting YOLO Failed. not set model file in config file [YOLO][...]')


    def setting_tesseract(self):
        if self.flask_app.config['TESSERACT'] and self.flask_app.config['TESSERACT']['PATH']:
            pytesseract.pytesseract.tesseract_cmd = self.flask_app.config['TESSERACT']['PATH']
        else:
            raise Exception('Setting Tesseract Failed. not set path in config file [TESSERACT][PATH]')
        
    
    def load_parseq(self):
        # self.parseq = torch.hub.load('./baudm/parseq', 'parseq', pretrained=True).eval()
        _local_path = os.path.join(os.path.abspath(os.path.dirname(__file__)) , '..', 'parseq')
        self.parseq = torch.hub.load(_local_path, 'parseq', pretrained=True, source='local').eval()
        # self.parseq = torch.load(os.path.join(os.path.abspath(os.path.dirname(__file__))  ,'model', 'parseq-bb5792a6.pt'))
        self.parseq_img_transform = SceneTextDataModule.get_transform(self.parseq.hparams.img_size)
    

    def logging(self, msg, msgtype='info'):
        if self.flask_app is not None:
            if msgtype == 'info':
                self.flask_app.logger.info(msg)
            elif msgtype == 'error':
                self.flask_app.logger.error(msg)
        return self
    

    def lib_extract_img_to_list(self, img):
        
        # texts = self.tesseract_parse(img)
        
        texts = self.parseq_parse(img)
        texts = [re.sub(r'[\D]+', '', _) for _ in texts]
        texts = [_ for _ in texts if _]
        # self.logging('[lib_extract_img_to_list] texts: {}'.format(texts))
        return texts


    def tesseract_parse(self, img):
        extracted = pytesseract.image_to_string(img, config=self.tesseract_config)
        texts =  extracted.splitlines()
        return self.get_datetime_format_handle(texts)
    

    def parseq_parse(self, img):
        
        img = Image.fromarray(img).convert('RGB')
        img = self.parseq_img_transform(img).unsqueeze(0)

        logits = self.parseq(img)

        pred = logits.softmax(-1)
        labels, confidence = self.parseq.tokenizer.decode(pred)
        return self.get_datetime_format_handle(labels)


    def get_datetime_format_handle(self, texts):
        results = []
        for txt in texts:
            _ = txt.lower()
            if re.search(r'[gmt\+\-\s]{1,5}\d+', _):
                results += re.split(r'[gmt\+\-\s]+\d{0,2}', _)
            else:
                results.append(_)
        # self.logging('[get_datetime_format_handle] texts: {} | parsed list: {}'.format(texts, results))
        return results
    

    def parse_rgbimg_lightblue_left(self, img):

        lower_bound = np.array([16,48,96])
        upper_bound = np.array([252,255,255])

        # lower_bound = np.array([36,48,72])
        # upper_bound = np.array([254,255,255])
        mask = cv2.inRange(img, lower_bound, upper_bound)

        height, width, _ = img.shape
        
        for y in range(height):
            for x in range(width):
                _avg = np.mean(img[y,x])
                _maxpooling_blue = np.max(img[max(y-3,0):y+4,max(x-4,0):x+5,2])
                if _maxpooling_blue < _avg:
                    mask[y,x] = 0
                _too_green = img[y,x,1] - 64 > img[y,x,2]
                _too_red = img[y,x,0] - 24 > _avg
                if _too_green or _too_red:
                    mask[max(y-3,0):y+4,max(x-4,0):x+5] = 0

        result = cv2.bitwise_and(img, img, mask=mask)
        result = cv2.bilateralFilter(result, 8, 25, 25) # 鄰域直徑 ,色彩相似性 ,空間相似性
        # plt.imshow(result)
        return result


    def get_img_center(self, img, zoom = 6):
        height, width, _ = img.shape
        center_height = height // 2
        gap_range = height // zoom // 2
        return img[center_height-gap_range:center_height+gap_range,8:-8,:]
    

    def make_img_bigger(self, img, ratio = 2):
        new_width = ratio * img.shape[1]
        new_height = ratio * img.shape[0]
        return cv2.resize(img, (new_width, new_height))


    def make_img_identifiable(self, img):
        kernel = np.array((
            [0.125, 0.125, 0.125],
            [0.125, 0.125, 0.125],
            [0.125, 0.125, 0.125],
        ), dtype="float32")
        img = cv2.filter2D(img, -1, kernel)
        # img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img


    def crope_panel_from_frame(self, frame, confident_threshold:float = 0.4) ->  tuple[Any, list]:
        """ use yolo model search a panel in frame

        return (
            croped: a numpy data which is panel liked in frame,
            xyxy: position shape of panel,
        )
        """
        results = self.model_yolo_glance(frame, verbose=False)
        for res in results:
            for box in res.boxes:
                xyxy = [int(_) for _ in box.xyxy[0]]
                cint = int(box.cls)
                cname = self.model_yolo_glance.names[cint]
                confident = float(box.conf)
                # if (cname == 'date' or cname == 'time') and confident > 0.5:
                if (cname == 'panel') and confident > confident_threshold:
                    croped = frame[xyxy[1]: xyxy[3], xyxy[0]: xyxy[2]]
                    return croped, xyxy
        
        return None, []
    

    def get_datetime_from_panel(self, panel, confident_threshold:float = 0.4) -> tuple[Any, list]:
        """ use yolo model get datetime in panel images
        
        """
        results = self.model_yolo_focus_on(panel)
        for res in results:
            for box in res.boxes:
                xyxy = [int(_) for _ in box.xyxy[0]]
                cint = int(box.cls)
                cname = self.model_yolo_focus_on.names[cint]
                confident = float(box.conf)
                # if (cname == 'date' or cname == 'time') and confident > 0.5:
                if (cname == 'datetime') and confident > confident_threshold:
                    croped = panel[xyxy[1]: xyxy[3], xyxy[0]: xyxy[2]]
                    return croped, xyxy

        return None, []
    

    def get_parsed_frame_by_path(self, id:str, path_image: str) -> tuple[Any, int, list[Any], list[str]]:
        """ parse the image by yolo and OCR algorithm then output results 

        return (
            img: numpy.array (  ),
            minute: int ( a number between 0 - 99 parsed by frame ),
            yolo_finds:  list[numpy.array] (  ),
            digits: str[] ( ocr result it will only included digital ),
        )
        """
        
        img = cv2.imread(path_image)
        parsed_minute = -1
        yolo_finds = []
        list_digits = []
        
        # now = datetime.utcnow()
        # print('img: ', img.shape)
        croped, xyxy = self.crope_panel_from_frame(img)
        
        if croped is not None:
            yolo_finds.append(croped)
            annotat = Annotator(img)
            annotat.box_label(xyxy, 'panel', color=(32,64,255))

            datetime, dt_xyxy = self.get_datetime_from_panel(croped)
            
            if datetime is not None:
                yolo_finds.append(datetime)
                croped_relate_width = croped.shape[1] / img.shape[1]
                croped_relate_hieght = croped.shape[0] / img.shape[0]
                self.label_annotat_by_deepth(annotat, [(xyxy,1,1), (dt_xyxy, croped_relate_width, croped_relate_hieght)], 'datetime')
                

                # img_datetime = self.parse_rgbimg_lightblue_left(img_datetime)
                # img_datetime = self.make_img_bigger(img_datetime, 2)
                # img_datetime = self.make_img_identifiable(img_datetime)
                
                # if minutes_difference(parsed_minute, now.minute) > 2:
                #     _saved_file_name = 'parsed_frame_{}_{}_{}.jpg'.format(pid, parsed_minute, ','.join(list_digits))
                #     _img_path = os.path.join(os.path.dirname(__file__), '..', 'debug', _saved_file_name)
                #     cv2.imwrite(_img_path, img_datetime)

                list_digits = self.lib_extract_img_to_list(datetime)
                

            else:
                img_center = self.get_img_center(croped, zoom=2)
                list_digits = self.lib_extract_img_to_list(img_center)


            parsed_minute = self.parse_minute_algo(list_digits)
            img = annotat.result()
        

        return img, parsed_minute, yolo_finds, list_digits
    


    def parse_minute_algo(self, list_digits):
        # 2023 99 28 04 09 02
        _len_digits = len(list_digits)
        if _len_digits == 1:
            _datetime_info = list_digits[0]
        elif _len_digits == 2:
            _datetime_info = list_digits[0] if len(list_digits[0]) >= len(list_digits[1]) else list_digits[1]
        else:
            return -1
            
        _len_info = len(_datetime_info)
            
        if _len_info > 12:
            # no split successful
            if _datetime_info[-1] == '0':
                _datetime_info = _datetime_info[:-1]
            if '0' in _datetime_info[12:]:
                _datetime_info = _datetime_info[:12]
        # YYYY.MM.DD HH:MM GMT+02
        # CCT yy/mm/dd hh:mm
        _last_two_digits = _datetime_info[-2:]
        if len(_last_two_digits) == 2:
            return int(_last_two_digits)

        # print('parse_minute_algo -1. list_digits: ', list_digits)
        return -1



    def label_annotat_by_deepth(self, annotat, list_depth_xy, name, color=(255,64,32)):
        if len(list_depth_xy) > 0:
            next_xyxy = list_depth_xy[0][0]
            _i = 1
            while (_i < len(list_depth_xy)):
                _loc = list_depth_xy[_i]
                _xyxy = _loc[0]
                # _ratio_width = _loc[1]
                # _ratio_height = _loc[2]
                # print('_ratio_width: ', _ratio_width)
                # print('_ratio_height: ', _ratio_height)
                next_xyxy[2] = next_xyxy[0] + _xyxy[2]
                next_xyxy[3] = next_xyxy[1] + _xyxy[3]

                next_xyxy[0] += _xyxy[0]
                next_xyxy[1] += _xyxy[1]
                _i += 1

            annotat.box_label(next_xyxy, name, color=color)

        return self







