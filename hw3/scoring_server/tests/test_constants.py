import datetime
import hashlib
from hw3.scoring_server import api

VALID_TOKEN = '178a72ced8d6581bc798d502288f9d29dd211c49231588656a1e72bc0123425d894808d42be9627d589b45851061173be3b215f44e503d0edc89ec6a6e65280f'  # noqa

VALID_SCORE_REQUEST = {
    'account': 'account1',
    'login': 'login',
    'method': 'online_score',
    'token': VALID_TOKEN,
    'arguments': {
        'phone': '71234567890',
        'email': 'aaa@some.hz',
        'first_name': 'Egor',
        'last_name': 'Borisov',
        'birthday': '01.01.1990',
        'gender': 1
    }
}

VALID_INTERESTS_REQUEST = {
    'account': 'account1',
    'login': 'login',
    'method': 'clients_interests',
    'token': VALID_TOKEN,
    'arguments': {
        'client_ids': [1, 2, 3, 4],
        'date': '01.01.2018'
    }
}


def generate_admin_token():
    time = datetime.datetime.now().strftime('%Y%m%d%H')
    return hashlib.sha512(time + api.ADMIN_SALT).hexdigest()
