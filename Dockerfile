# FROM ubuntu:22.04
FROM python:3.9 AS builder

RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install ffmpeg libsm6 libxext6 libgl1 -y
RUN mkdir -p /video_observer
# RUN apt-get install supervisor -y
# RUN mkdir -p /etc/supervisor/conf.d
# COPY supervisord.conf /etc/supervisor/conf.d/

# RUN apt install python3.9 -y
# RUN apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev -y

WORKDIR /video_observer
COPY ./requirements.txt /video_observer/requirements.txt

RUN pip install -r requirements.txt --no-cache-d


# CMD celery -A bg_celery.tasks worker --loglevel=INFO --concurrency=12 --purge --discard
# CMD ["python3", "app.py"]
# CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]
# CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
CMD ["echo", "hello"]
