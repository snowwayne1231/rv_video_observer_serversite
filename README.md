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


## 2. Runing:
* Install and Launch Redis.
By Docker:
```shell
docker pull redis/redis-stack
docker run -d --name [redis-stack] -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
docker start [redis-stack]
```
Basic on redhot:
```shell
sudo apt-get update
sudo apt-get install redis
redis-server /etc/redis/myconfig.conf
```
Basic on centos:
```shell
sudo yum install epel-release
sudo yum install redis -y
sudo service redis start
```

---
* Install python 3.9 and later.
Install or check python 3.9
```shell
wget https://www.python.org/ftp/python/3.9.7/Python-3.9.7.tgz
tar zxvf Python-3.9.7.tgz
cd Python-3.9.7
./configure
make
sudo make altinstall
python3.9 --version
```
Check openssl version
```shell
openssl version
```
If version is lower OpenSSL 1.1.1e
```shell
wget https://www.openssl.org/source/openssl-1.1.1w.tar.gz --no-check-certificate
tar -xf openssl-1.1.1w.tar.gz
cd openssl-1.1.1w
./config --prefix=/usr/local/openssl --openssldir=/usr/local/openssl
sudo make
sudo make install
echo "/usr/local/openssl/lib" | sudo tee /etc/ld.so.conf.d/openssl.conf
sudo ldconfig
/usr/local/openssl/bin/openssl version
sudo mv /usr/bin/openssl ~/tmp
sudo ln -s /usr/local/openssl/bin/openssl /usr/bin/openssl
```

---
* Create new user for this project
```shell
sudo useradd vobserver
sudo passwd vobserver
su vobserver
```

---
* Project files
Git clone
```shell
cd /[some-where]
mkdir rv-video-observer
cd rv-video-observer
git clone https://github.com/snowwayne1231/rv_video_observer_serversite.git
```

---
* Build up a python virual environment
```shell
python3.9 -m venv venv
source venv/bin/activate
cd rv_video_observer_serversite
pip install -r requeirements.txt
```

---
* Run Main flask app.
```shell
cd server
flask --app app run --debug
# or
python app.py
```

---
* Run Celery workers for capture live streaming frames.
```shell
cd server
celery -A bg_celery.tasks worker --loglevel=WARNING --concurrency=12 --purge --discard
```

---
* Docker Compose On Production env
```shell
docker build --tag=rv/video/observer/core:1.0.0 .
docker-compose up -d
```

---
* Upgrades

```Shell
docker-compose up -d --build observer
docker image rm rv/video/observer/app:1.x.x
```

---
* some docker cmd
```shell

docker pull redis
docker network create -d bridge --attachable observer-net
docker run -dp 6379:6379 --name ob-redis redis
docker network connect observer-net ob-redis --alias ob-redis 

docker run --rm -p 5000:5000 --expose 5000 --network observer-net -it --entrypoint /bin/bash video-observer

docker container ls --format "table {{.ID}}\t{{.Names}}\t{{.Ports}}" -a
```

---

## 3. UAT Deployment record
* 請SE協助打開與 Docker 相關的網域

---
* UAT環境 有外網限制, 必須加入 proxy:
修改 Dockerfile 加入:
``` shell
ENV http_proxy http://xxxx
ENV https_proxy http://xxxx
# before apt-get update
```

執行 build core
``` shell
export http_proxy="http://xxxx";
export https_proxy="http://xxxx";

docker build --tag=rv/video/observer/core:1.0.0 . --network host
```

修改 docker-compose.yml 
``` shell
# add parameter
serveice
  receiver
    build
      network: host
      args:
        - http_proxy: http://xxxx
        - https_proxy: http://xxxx
```
執行 docker compose up
``` shell
docker-compose up -d
```


