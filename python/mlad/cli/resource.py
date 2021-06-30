import sys
from collections import defaultdict
from mlad.cli.libs import utils
from mlad.api import API
from mlad.api.exception import APIError, NotFound



def node_list(nodes, no_trunc):
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
            capacity = status['capacity']
            used = status['used']
            allocatable = status['allocatable']
            if not no_trunc:
                capacity = round(capacity, 1)
                used = round(used, 1) if not used == None else 'NotReady'
                allocatable = round(allocatable, 1)
            else:
                used = status['used'] if not used == None else 'NotReady'
            percentage = int(allocatable / capacity * 100) if capacity else 0
            type = get_unit(type)
            columns.append((node if not i else '', type, capacity, used,
                            f'{allocatable}({percentage}%)'))
    utils.print_table(columns, 'No attached node.', 0 if no_trunc else 32)

def service_list(no_trunc):
    config = utils.read_config()
    project_key = utils.project_key(utils.get_workspace())
    try:
        with API(config.mlad.address, config.mlad.token.user) as api:
            res = api.project.resource(project_key)
    except APIError as e:
        print(e)
        sys.exit(1)
    columns = [('SERVICE', 'MEMORY(Mi)', 'CPU(cores)', 'GPU(#)')]

    for service, resources in res.items():
        if resources['mem'] == None:
            gpu = round(resources['gpu'], 1) if not no_trunc else resources['gpu']
            columns.append((service, 'NotReady', 'NotReady', gpu))
        else:
            if not no_trunc:
                mem = round(resources['mem'], 1)
                cpu = round(resources['cpu'], 1)
                gpu = round(resources['gpu'], 1)
                columns.append((service, mem, cpu, gpu))
            else:
                columns.append((service, resources['mem'], resources['cpu'], resources['gpu']))
    utils.print_table(columns, 'Cannot find running services.', 0 if no_trunc else 32, False)


def project_list(no_trunc):
    config = utils.read_config()
    columns = [('PROJECT', 'MEMORY(Mi)', 'CPU(cores)', 'GPU(#)', 'STATUS')]
    res = {}
    try:
        with API(config.mlad.address, config.mlad.token.user) as api:
            projects = api.project.get()
            for project in projects:
                key = project['key']
                key = key.replace('-', '')
                name = project['name']
                resources = api.project.resource(key)
                res[name] = resources
    except APIError as e:
        print(e)
        sys.exit(1)

    for project, services in res.items():
       used = defaultdict(lambda: 0)
       collect = {'used': used, 'status': 'Collected'}
       for service, resources in services.items():
           if resources['mem'] == None:
               collect['status'] = 'NotReady'
           else:
               collect['used']['mem'] += resources['mem']
               collect['used']['cpu'] += resources['cpu']
           collect['used']['gpu'] += resources['gpu']

       mem = collect['used']['mem']
       cpu = collect['used']['cpu']
       gpu = collect['used']['gpu']

       mem = mem if no_trunc else round(mem, 1)
       cpu = cpu if no_trunc else round(cpu, 1)
       gpu = gpu if no_trunc else round(gpu, 1)

       columns.append((project, mem, cpu, gpu, collect['status']))
    utils.print_table(columns, 'Cannot find running projects.', 0 if no_trunc else 32, False)
