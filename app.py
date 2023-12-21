from flask import Flask, request, render_template, abort, make_response, send_from_directory
from socketctl import create_video_socket
import logging
# import eventlet
import os
import yaml


logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s](%(levelname)s) %(message)s',
        }
    },
    'handlers': {
        'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})



current_path = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder="frontend/static")
with open(os.path.join(current_path, 'config.yaml')) as f:
    cdata = yaml.safe_load(f.read())
    app.config.update(cdata)

app.config['SECRET_KEY'] = 'secretkey'
app.config['Allow-Origin'] = '*'

sio = create_video_socket(app)


@app.route("/")
def index():
    return send_from_directory(os.path.join(current_path), 'frontend/index.html')

@app.route("/<path:filename>")
def main(filename):
    # return render_template('index.html')
    return send_from_directory(os.path.join(current_path, 'frontend'), filename)

@app.route("/public/<path:filename>")
def public_path(filename):
    return send_from_directory(os.path.join(current_path, 'public'), filename)



if __name__ == '__main__':
    try:

        sio.run(app, port=5000, debug=app.config['DEBUG'])
        # wsgi_app = socketio.WSGIApp(sio, app)
        # eventlet.wsgi.server(eventlet.listen(('', 5000)), wsgi_app)

    except KeyboardInterrupt:
        # sio.exit_background_ocrtask()
        app.logger.error('KeyboardInterrupt.')

    except Exception as error:
        # sio.exit_background_ocrtask()
        app.logger.error(str(error))

    finally:

        sio.exit_background_ocrtask()
        # sio.stop()


    