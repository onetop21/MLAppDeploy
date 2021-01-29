import sys
import os
from urllib.parse import urlparse
from datetime import datetime
from omegaconf import OmegaConf
from mlad.cli.libs import utils
from mlad.core.default import config as default_config
from mlad.api import API

def create(username, expired):
    config = utils.read_config()
    with API(utils.to_url(config.mlad), config.mlad.token.admin) as api:
        user_token = api.auth.token_create(username)
    print('User Token :', user_token)

def info(token):
    config = utils.read_config()
    base_token = config.mlad.token.user or config.mlad.token.admin
    with API(utils.to_url(config.mlad), base_token) as api:
        result = api.auth.token_verify(token)
    if result['result']:
        for k, v in result['data'].items():
            if k in ['created', 'expired']:
                v = datetime.fromisoformat(v)
            print(f"{k.upper():16} {v}")
    else:
        print('Invalid token.')
