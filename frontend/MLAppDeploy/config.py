import sys, os
import MLAppDeploy.libs.utils as utils
import MLAppDeploy.default as default

def dict_to_graph(vars, base={}):
    config = base
    for ckeys in vars:
        keys = ckeys.split('.')
        head = config
        for key in keys[:-1]:
            head[key] = head[key] if key in head else {}
            head = head[key]
        if vars[ckeys]:
            head[keys[-1]] = vars[ckeys] 
        elif len(keys):
            if keys[-1] in head: del head[keys[-1]]
        else:
            if keys[-1] in config: del config[keys[-1]]
    return config

def get_value(config, keys, stack=[]):
    if not keys:
        data = []
        for key in config:
            if isinstance(config[key], dict):
                data = data + get_value(config[key], keys, stack + [key])
            else:
                data.append(('.'.join(stack + [key]), config[key]))
        return data
    else:
        head = config
        try:
            for key in keys.split('.'):
                stack.append(key)
                head = head[key]
            if not isinstance(head, dict):
                return head
            else:
                print('Value is expandable.', file=sys.stderr)
        except KeyError:
            print('Cannot find config key.', file=sys.stderr)
        sys.exit(1)

def init(username, address):
    utils.generate_empty_config()
    set(*(
        'account.username=%s'%username, 
        'docker.host=%s:2375'%address,
        'docker.registry=%s:5000'%address,
        's3.endpoint=%s:9000'%address
    ))
    get(None)

def set(*args):
    try:
        vars = dict([ var.split('=') for var in args ])
    except ValueError as e:
        print('Argument format is not valid.', file=sys.stderr)
        sys.exit(1)

    config = default.config(utils.read_config())
    config = dict_to_graph(vars, config)

    utils.write_config(config)

def get(keys):
    config = default.config(utils.read_config())
    data = get_value(config, keys)
    if isinstance(data, list):
        print('{:24} {:32}'.format('KEY', 'VALUE'))
        for key, value in data:
            #if key and value: print('{}={}'.format(key, value))
            if key and value: print('{:24} {:32}'.format(key, value))
    else:
        print(data)
