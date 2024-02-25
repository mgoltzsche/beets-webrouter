from flask import Blueprint

bp = Blueprint('webrouterfavicon_bp', __name__, static_folder='static',
        static_url_path='/static')

@bp.route('')
def favicon():
    return bp.send_static_file('favicon.ico')
