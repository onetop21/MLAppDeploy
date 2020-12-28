import sys
import os
import glob
from mladcli.default import project as default_project
from mladcli.libs import docker_controller as controller
from mladcli.libs import utils

def get_project_file_completion(ctx, args, incomplete):
    files = glob.glob(f"{incomplete}*" or '*')    
    subcommands = [f"{_}/" for _ in files if os.path.isdir(_)]
    subcommands += [_ for _ in files if _.endswith('.yaml') or _.endswith('.yml')]
    return subcommands

def get_dir_completion(ctx, args, incomplete):
    files = glob.glob(f"{incomplete}*" or '*')    
    subcommands = [f"{_}/" for _ in files if os.path.isdir(_)]
    return subcommands

def get_node_list_completion(ctx, args, incomplete):
    nodes = controller.node_list()
    hostnames = [_.attrs['Description']['Hostname'] for _ in nodes]
    ids = [_.attrs['ID'][:controller.SHORT_LEN] for _ in nodes] if incomplete else []
    return [_ for _ in hostnames + ids if _.startswith(incomplete)]

def get_node_label_completion(ctx, args, incomplete):
    node = controller.node_get(args[2])
    keys = [f'{key}' for key, value in node.attrs['Spec']['Labels'].items()]
    return [_ for _ in keys if _.startswith(incomplete)]
    
def get_config_key_completion(ctx, args, incomplete):
    config = utils.read_config()
    def compose_keys(config, stack=[]):
        keys = []
        for k, v in config.items():
            stack.append(k)
            if isinstance(v, dict):
                keys += compose_keys(config[k], stack.copy())
            else:
                keys.append('.'.join(stack))
            stack.pop(-1)
        return keys
    return [_ for _ in compose_keys(config) if _.startswith(incomplete)] 

def get_image_list_completion(ctx, args, incomplete):
    images, dummies = controller.image_list()
    repos = [':'.join(_[1:3]) for _ in images]
    ids = [_[0] for _ in images] if incomplete else []
    return [_ for _ in repos + ids if _.startswith(incomplete)]

def get_stopped_services_completion(ctx, args, incomplete):
    project_file = [_ for _ in [args[i+1] for i, _ in enumerate(args[:-1]) if _ in ['-f', '--file']] if os.path.isfile(_)]
    if project_file: utils.apply_project_arguments(project_file[-1], None)
    project = utils.get_project(default_project)
    running_list = controller.get_running_services(project['project'])
    service_list = [_ for _ in project['services'] if _.startswith(incomplete) and not _ in running_list]
    return service_list

def get_running_services_completion(ctx, args, incomplete):
    project_file = [_ for _ in [args[i+1] for i, _ in enumerate(args[:-1]) if _ in ['-f', '--file']] if os.path.isfile(_)]
    if project_file: utils.apply_project_arguments(project_file[-1], None)
    project = utils.get_project(default_project)
    return [_ for _ in controller.get_running_services(project['project']) if _.startswith(incomplete)]

def get_running_services_tasks_completion(ctx, args, incomplete):
    project_file = [_ for _ in [args[i+1] for i, _ in enumerate(args[:-1]) if _ in ['-f', '--file']] if os.path.isfile(_)]
    if project_file: utils.apply_project_arguments(project_file[-1], None)
    project = utils.get_project(default_project)
    candidates = controller.get_running_services(project['project']) + controller.get_running_tasks(project['project'])
    return [_ for _ in candidates if _.startswith(incomplete)]

