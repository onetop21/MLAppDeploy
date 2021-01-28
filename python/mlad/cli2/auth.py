import sys
import os
from urllib.parse import urlparse
from datetime import datetime
from omegaconf import OmegaConf
from mlad.cli2.libs import utils
from mlad.core.default import config as default_config
from mlad.api import auth as auth_api

def create(username, expired):
    config = utils.read_config()
    user_token = auth_api.token_create(config.mlad.token.admin, username)
    print('User Token :', user_token)

def verify(token):
    config = utils.read_config()
    result = auth_api.token_verify(token)
    if result['result']:
        for k, v in result['data'].items():
            if k in ['created', 'expired']:
                v = datetime.fromisoformat(v)
            print(f"{k.upper():16} {v}")
    else:
        print('Invalid token.')
