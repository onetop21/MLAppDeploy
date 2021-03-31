import sys
import os
from urllib.parse import urlparse
from requests.exceptions import HTTPError
from datetime import datetime
from omegaconf import OmegaConf
from mlad.cli.libs import utils
from mlad.core.default import config as default_config
from mlad.api import API

def create(username, expired):
    config = utils.read_config()
    try:
        with API(utils.to_url(config.mlad), config.mlad.token.admin) as api:
            user_token = api.auth.token_create(username)
        print('User Token :', user_token)
    except HTTPError as e:
        print('Failed to decode token.', file=sys.stderr)

def login(token):
    config = utils.read_config()
    try:
        with API(utils.to_url(config.mlad), token) as api:
            result = api.auth.token_verify(token)
    except HTTPError as e:
        print('Failed to decode token.', file=sys.stderr)
        return
    if result['result']:
        for k, v in result['data'].items():
            if k == 'role':
                if v == 'admin':
                    config = default_config['client'](utils.read_config())
                    args = [f'mlad.token.admin={token}']
                    config = OmegaConf.merge(config, OmegaConf.from_dotlist(args))
                    utils.write_config(config)
                    print('Logged in to administrator.')
                elif v == 'user':
                    config = default_config['client'](utils.read_config())
                    args = [f'mlad.token.user={token}']
                    config = OmegaConf.merge(config, OmegaConf.from_dotlist(args))
                    utils.write_config(config)
                    info(token)
                else:
                    print('Invalid role.', file=sys.stderr)
    else:
        print('Invalid token.', file=sys.stderr)

def logout():
    config = utils.read_config()
    try:
        with API(utils.to_url(config.mlad), config.mlad.token.user) as api:
            result = api.auth.token_verify(config.mlad.token.user)
    except HTTPError as e:
        print('Failed to decode token.', file=sys.stderr)
        return
    if result['result']:
        for k, v in result['data'].items():
            if k in ['username']:
                args = [f'mlad.token.user=']
                config = OmegaConf.merge(config, OmegaConf.from_dotlist(args))
                utils.write_config(config)
                print(f"Logged out User[{v}]")
    else:
        print('Invalid token or already logged out.', file=sys.stderr)

def info(token=None):
    config = utils.read_config()
    if not token:
        for token in [config.mlad.token.admin, '-', config.mlad.token.user]:
            if token == '-': print('---')
            elif token: info(token)
    else:
        try:
            with API(utils.to_url(config.mlad), config.mlad.token.admin or config.mlad.token.user) as api:
                result = api.auth.token_verify(token)
        except HTTPError as e:
            print('Failed to decode token.', file=sys.stderr)
            return
        if result['result']:
            for k, v in result['data'].items():
                if k in ['created', 'expired']:
                    v = datetime.fromisoformat(v)
                print(f"{k.upper():16} {v}")
        else:
            print('Invalid token.')

