import sys
import MLAppDeploy.utils as utils

obj = {
    'project': {
        'name': 'Unknown',
        'version': '0.0.0',
        'author': 'Unknown',
    },
    'workspace': {
        'depends': {},
        'env': {},
        'ignore': [],
        'entrypoint': 'sh',
        'arguments': '',
    },
    'services': {}
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
