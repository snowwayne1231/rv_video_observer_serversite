# RV Video Observer
---
a tool for observing video's datetime
observing whether datetime which in live videos is keeping right 

## 1. Requirement:
---
* Python 3.9.x
* YOLO v8  (https://github.com/ultralytics/ultralytics)
* tesseract  (https://github.com/tesseract-ocr/tesseract)  (棄用)
* pytesseract  (https://github.com/madmaze/pytesseract)  (棄用)
* parseq  (https://github.com/baudm/parseq)
* Redis (https://redis.io/)
* Celery 5.3.x (https://docs.celeryq.dev/en/stable/)

---


## 2. Install and Runing:
* Redis:

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

docker network create -d bridge --attachable observer-net
docker network connect observer-net ob-redis --alias ob-redis 
docker run --rm -p 5000:5000 --expose 5000 --network observer-net -it --entrypoint /bin/bash video-observer
docker container ls --format "table {{.ID}}\t{{.Names}}\t{{.Ports}}" -a
```

---

## 3. UAT Deployment record
* 請SE協助打開與 Docker 相關的網域
- 1. linux apt-get 相關需要
- 2. docker 相關需要
- 3. pip 相關需要
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

docker build --no-cache --tag=rv/video/observer/core:1.0.0 . --network host
```

修改 docker-compose.yml (uat-docker-compose.yml)
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
docker-compose -f docker-compose.yml -f uat-docker-compose.yml up -d
```


---

## 4. Folder Construct
- bg_celery **(使用celery多線處理 rtmp 任務)**
- classes 
  - | - `data.py`  **(儲存/取用data )**
  - | - `internet.py` **(外部request functions)**
  - | - `ocr.py` **(OCR algorithms of handling frame from RTMP)**
  - | - `timeformula.py` **(Functions of Specific time formats)**

- configs **(Main service config)**
- debug **(Temporarily save results when debug mode on)**
- frontend **(Out of created by react)**
- model
  - | - yolo **(trained yolo models)**
  - | - `parseq.pt` **(trained parseq model)**
- nginx.conf.d
  - | - ssl **(configurations and certificates)**
  - | - `default.conf` **(sub blocks in configuration of nginx http)**
- parseq **(library reference)**
- public **(folder of exposed http request and put generated pictures from RTMP)**
- `app.py` **(Main python starter)**
- `docker-compose.yml` 
- `Dockerfile`
- `Dockerfile-celery`
- `Dockerfile-observer`
- `socketctl.py` **(Web socket controller)**

---

## 5. PROD maintenance
* 切換 串流影片的設定來源 找到 configs/config.yaml 修改
```yaml
VIDEO:
  URL: "http://43.206.22.82:8087/api/bavideo/getAllWhite" -> 欲修改的API位置
```
```shell
docker-compose restart
```

---

* 如果平板類型有大幅改動 想修正YOLO模型
1. 先將新的 pt 權重檔放置 model/yolo/ 底下
2. 接著修改 configs/config.yaml 檔案內的名稱使之對應
```yaml
YOLO:
  GLANCE: "search_panel.pt" -> 用以快速辨識平板位置
  FOCUSON: "get_datetime.pt" -> 從已找到的平板中找尋時間格式文字
```
```shell
docker-compose restart
```

---

* 修改nginx設定 找到檔案 nginx.conf.d/default.conf
```nginx
server {
  listen 443 ssl;
  listen [::]:443 ssl;

  include /etc/nginx/conf.d/ssl/self-signed.conf; # SSL設定

  # proxy to local main server
  location / {
    proxy_http_version 1.1;
    proxy_pass http://observer:5000;
  }
}
```

* 修改SSL憑證 在 nginx.conf.d 目錄下
nginx.conf.d
+-- ssl
| -- `dhparam.pem` -> 替換 Diffie–Hellman 鑰匙
| -- `ns.crt` -> 替換憑證檔
| -- `ns.key` -> 替換金鑰
| -- `self-signed.conf` -> 相關SSL設定
```shell
docker restart [nginx-container]
```

---

* Docker容器如有設定問題(如network,extend)請建立新yaml檔
```shell
mkdir prod-docker.compose.yml
```
並依照需求更改 (以下為範例uat-docker-compose.yml)
```yaml
services:
  observer:
    environment:
      - http_proxy=
      - https_proxy=
      - HTTP_PROXY=
      - HTTPS_PROXY=
  receiver:
    build:
      network: host
      args:
        - HTTP_PROXY=
        - HTTPS_PROXY=
```
接著將舊有container清除並建立新設定
```shell
docker-compose down
docker-compose -f docker-compose.yml -f prod-docker.compose.yml up -d
```