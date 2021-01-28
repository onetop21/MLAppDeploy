import sys
import os
from urllib.parse import urlparse
from omegaconf import OmegaConf
from mlad.cli2.libs import utils
from mlad.core.default import config as default_config
from mlad.api.auth import token_create

def create(username, expired):
    config = utils.read_config()
    user_token = token_create(config.mlad.token.admin, username)
    print('User Token :', user_token)

def verify(token):
    pass
