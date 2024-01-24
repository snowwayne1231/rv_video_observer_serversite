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


def create_flask_app():
    current_path = os.path.abspath(os.path.dirname(__file__))

    app = Flask(__name__, static_folder="frontend/static")
    with open(os.path.join(current_path, 'config.yaml')) as f:
        cdata = yaml.safe_load(f.read())
        app.config.update(cdata)

    app.config['SECRET_KEY'] = 'secretkey'
    app.config['Allow-Origin'] = '*'

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
    
    return app



def create_merged_app(flask_app):
    sio = create_video_socket(flask_app)
    
    return sio



def create_gunicorn_service():
    f_app = create_flask_app()
    create_merged_app(f_app)
    return f_app



if __name__ == '__main__':
    logging.info('[Dev] Start By main process.')
    try:
        
        app = create_flask_app()
        s_app = create_merged_app(app)
        s_app.run(app, port=5000, debug=app.config['DEBUG'])
        # wsgi_app = socketio.WSGIApp(sio, app)
        # eventlet.wsgi.server(eventlet.listen(('', 5000)), wsgi_app)

    except KeyboardInterrupt:
        
        logging.error('KeyboardInterrupt.')

    except Exception as error:
        
        logging.error(str(error))

    finally:

        s_app.exit_background_ocrtask()
        # sio.stop()
else:
    
    logging.info('[PROD] Start By wsgi service.')
    app = create_gunicorn_service()

    