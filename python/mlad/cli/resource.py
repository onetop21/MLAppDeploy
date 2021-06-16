import sys
from mlad.cli.libs import utils
from mlad.api import API
from mlad.api.exception import APIError, NotFound

def list(nodes, no_trunc):
    config = utils.read_config()
    try:
        with API(config.mlad.address, config.mlad.token.admin) as api:
            res = api.node.resource(nodes)
    except APIError as e:
        print(e)
        sys.exit(1)
    columns = [('HOSTNAME', 'TYPE', 'CAPACITY', 'USED', 'ALLOCATABLE(%)')]

    def get_unit(type):
        res = ''
        if type == 'mem':
            res = f'{type}(Mi)'
        elif type == 'cpu':
            res = f'{type}(cores)'
        elif type == 'gpu':
            res = f'{type}(#)'
        return res

    for node, resources in res.items():
        for i, type in enumerate(resources):
            status = resources[type]
            capacity = round(status['capacity'], 1)
            used = round(status['used'], 1)
            allocatable = round(status['allocatable'], 1)
            percentage = int(allocatable / capacity * 100)
            type = get_unit(type)
            columns.append((node if not i else '', type, capacity, used,
                            f'{allocatable}({percentage}%)'))

    utils.print_table(columns, 'No attached node.', 0 if no_trunc else 32)