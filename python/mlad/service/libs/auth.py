import sys
import os
import time
import datetime
import hashlib
import uuid
import base64
import psutil
from mlad.service import exception
from mlad.service.libs import utils

# #Token
# Admin: 
#  admin:{created_date}
# User:
#  user:{config['user']['name']}:{created_date}:{expired_date}

def ISOFormat(_):
    return _.astimezone().isoformat()

def fixed_datetime():
    return datetime.datetime.strptime('2021-01-01 00:00:00', '%Y-%m-%d %H:%M:%S')

def process_uptime():
    if utils.is_debug_mode(): return fixed_datetime().astimezone()
    return datetime.datetime.fromtimestamp(psutil.Process().create_time()).astimezone()

def create_datetime():
    if utils.is_debug_mode(): return fixed_datetime()
    return datetime.datetime.now()

def get_admin_key(config):
    if utils.is_debug_mode(): return uuid.UUID('0' * 32)
    return config['auth_keys']['admin']
 
def get_user_key(config):
    if utils.is_debug_mode(): return uuid.UUID('0' * 32)
    return config['auth_keys']['user']
    
def decode_token(token):
    try:
        decoded = base64.b64decode(token.encode() if isinstance(token, str) else token).decode()
        role, _ = decoded.split(';', 1)
        if role == 'admin':
            created, hash_key = _.split(';')
            return {
                'role': 'admin',
                'created': datetime.datetime.fromisoformat(created),
                'hash_key': hash_key
            }
        elif role == 'user':
            username, created, expired, hash_key = _.split(';')
            return {
                'role': 'user',
                'username': username,
                'created': datetime.datetime.fromisoformat(created),
                'expired': datetime.datetime.fromisoformat(expired),
                'hash_key': hash_key
            }
        else:
            raise exception.TokenError('Invalid role in token.')
    except UnicodeDecodeError:
        raise exception.TokenError('Invalid token.')
    
def verify_token(token):
    if not isinstance(token, dict): raise TypeError('Invalid token(decoded) type.')
    config = utils.read_config()
    admin_key = get_admin_key(config)
    user_key = get_user_key(config)
    if token['role'] == 'admin':
        if token['created'] != process_uptime(): 
            print('Expired token.', file=sys.stderr)
            return False
        key = f"{token['role']};{ISOFormat(token['created'])}"
        postfix_hash = hashlib.sha1(f"{key};{admin_key}".encode()).hexdigest()
    elif token['role'] == 'user':
        if token['expired'] < datetime.datetime.now().astimezone():
            print('Expired token.', file=sys.stderr)
            return False
        key = f"{token['role']};{token['username']};{ISOFormat(token['created'])};{ISOFormat(token['expired'])}"
        postfix_hash = hashlib.sha1(f"{key};{user_key}".encode()).hexdigest()
    else:
        raise exception.TokenError('Invalid Role in Token.')
    return postfix_hash == token['hash_key']

def generate_admin_token():
    config = utils.read_config()
    admin_key = get_admin_key(config)
    key = f"admin;{ISOFormat(process_uptime())}"
    postfix_hash = hashlib.sha1(f"{key};{admin_key}".encode())
    token = f"{key};{postfix_hash.hexdigest()}"
    return base64.b64encode(token.encode())

def generate_user_token(username):
    config = utils.read_config()
    user_key = get_user_key(config)
    expired = '2099-12-31 23:59:59'
    expired_date = datetime.datetime.strptime(expired, '%Y-%m-%d %H:%M:%S')
    key = f"user;{username};{ISOFormat(create_datetime())};{ISOFormat(expired_date)}"
    postfix_hash = hashlib.sha1(f"{key};{user_key}".encode())
    token = f"{key};{postfix_hash.hexdigest()}"
    return base64.b64encode(token.encode())

if __name__ == '__main__':
    from pprint import pprint
    admin_token = generate_admin_token()
    print('Admin Token :', admin_token)
    user_token = generate_user_token('onetop21')
    print('User Token :', user_token)


    time.sleep(3)

    decoded = decode_token(admin_token)
    pprint(decoded)
    print(verify_token(decoded))

    decoded = decode_token(user_token)
    pprint(decoded)
    print(verify_token(decoded))
