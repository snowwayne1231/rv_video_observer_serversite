# RV Video Observer
---
a tool for observing video's datetime
whether datetime is keep right in the live videos

## 1. Requirement:
---
* Python 3.9.x
* YOLO v8  (https://github.com/ultralytics/ultralytics)
* tesseract  (https://github.com/tesseract-ocr/tesseract)
* pytesseract  (https://github.com/madmaze/pytesseract)
* parseq  (https://github.com/baudm/parseq)
* Redis (https://redis.io/)

---
## Server site


### Runing:
* Install or Launch Redis By Docker.
```shell
docker run -d --name [redis-stack] -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
```
```shell
docker start [redis-stack]
```


* Run Main flask app.
```shell
cd server
flask --app app run --debug

or

python app.py
```

* Run Celery workers for capture live streaming frames.
```shell
cd server
celery -A bg_celery.tasks worker --loglevel=INFO --concurrency=12 --purge --discard
```

