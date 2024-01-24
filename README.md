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
* 1. Install and Launch Redis.
** 1.1 By Docker:
```shell
docker pull redis/redis-stack
docker run -d --name [redis-stack] -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
docker start [redis-stack]
```
** 1.2 Basic on redhot:
```shell
sudo apt-get update
sudo apt-get install redis
redis-server /etc/redis/myconfig.conf
```
** 1.3 Basic on centos:
```shell
sudo yum install epel-release
sudo yum install redis -y
sudo service redis start
```

* 2. Install python 3.9 and later.
** 2.1 install or check python 3.9
```shell
wget https://www.python.org/ftp/python/3.9.7/Python-3.9.7.tgz
tar zxvf Python-3.9.7.tgz
cd Python-3.9.7
./configure
make
sudo make altinstall
python3.9 --version
```
** 2.2 check openssl version
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

* 3. create new user for this project
```shell
sudo useradd vobserver
sudo passwd vobserver
su vobserver
```

* 4. Project files
** 4.1 git clone
```shell
cd /[some-where]
mkdir rv-video-observer
cd rv-video-observer
git clone https://github.com/snowwayne1231/rv_video_observer_serversite.git
```

* 5. Build up a python virual environment
** 5.1
```shell
python3.9 -m venv venv
source venv/bin/activate
cd rv_video_observer_serversite
pip install -r requeirements.txt
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
celery -A bg_celery.tasks worker --loglevel=WARNING --concurrency=12 --purge --discard
```


* Docker Compose
```shell
docker-compose up -d
```



* some docker cmd
```shell
docker build -t video-observer .


docker pull redis
docker network create -d bridge --attachable observer-net
docker run -dp 6379:6379 --name ob-redis redis
docker network connect observer-net ob-redis --alias ob-redis 


docker run --rm -p 5000:5000 --expose 5000 --network observer-net -it --entrypoint /bin/bash video-observer

docker container ls --format "table {{.ID}}\t{{.Names}}\t{{.Ports}}" -a
```
