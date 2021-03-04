import sys
import os
import glob
from omegaconf import OmegaConf
from mlad.core.default import project as default_project
from mlad.core.docker import controller as controller
from mlad.cli.libs import utils

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
    config = utils.read_config()
    cli = controller.get_api_client(config['docker']['host'])
    nodes = [controller.inspect_node(_) for _ in controller.get_nodes(cli).values()]
    hostnames = [_['hostname'] for _ in nodes]
    ids = [_['ID'][:controller.SHORT_LEN] for _ in nodes] if incomplete else []
    return [_ for _ in hostnames + ids if _.startswith(incomplete)]

def get_node_label_completion(ctx, args, incomplete):
    config = utils.read_config()
    node_key = args[args.index('label')+1]
    cli = controller.get_api_client(config['docker']['host'])
    node = controller.inspect_node(controller.get_node(cli, node_key))
    keys = [f'{key}' for key, value in node['labels'].items()]
    return [_ for _ in keys if _.startswith(incomplete)]
    
def get_config_key_completion(ctx, args, incomplete):
    config = OmegaConf.to_container(utils.read_config(), resolve=True)
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
    config = utils.read_config()
    cli = controller.get_api_client(config['docker']['host'])
    images = controller.get_images(cli)
    inspects = [controller.inspect_image(_) for _ in images]
    repos = [f"{_['repository']}{':'+_['tag'] if _['tag'] else ''}" for _ in inspects]
    if incomplete:
        separated_repos = [__ for _ in repos for __ in _.split(':')]
        ids = [_['short_id'] for _ in inspects]
        return [_ for _ in set(separated_repos+ids) if _.startswith(incomplete)]
    else:
        return [_ for _ in repos if _.startswith(incomplete)]

def get_stopped_services_completion(ctx, args, incomplete):
    config = utils.read_config()
    cli = controller.get_api_client(config['docker']['host'])
    project_file = [_ for _ in [args[i+1] for i, _ in enumerate(args[:-1]) if _ in ['-f', '--file']] if os.path.isfile(_)]
    if project_file: utils.apply_project_arguments(project_file[-1], None)

    project_key = utils.project_key(utils.get_workspace())
    services = controller.get_services(cli, project_key)
    return [_ for _ in project['services'] if _.startswith(incomplete) and not _ in services]

def get_running_services_completion(ctx, args, incomplete):
    config = utils.read_config()
    cli = controller.get_api_client(config['docker']['host'])
    project_file = [_ for _ in [args[i+1] for i, _ in enumerate(args[:-1]) if _ in ['-f', '--file']] if os.path.isfile(_)]
    if project_file: utils.apply_project_arguments(project_file[-1], None)

    project_key = utils.project_key(utils.get_workspace())
    services = controller.get_services(cli, project_key)
    return [_ for _ in services if _.startswith(incomplete)]

def get_running_services_tasks_completion(ctx, args, incomplete):
    config = utils.read_config()
    cli = controller.get_api_client(config['docker']['host'])
    project_file = [_ for _ in [args[i+1] for i, _ in enumerate(args[:-1]) if _ in ['-f', '--file']] if os.path.isfile(_)]
    if project_file: utils.apply_project_arguments(project_file[-1], None)

    project_key = utils.project_key(utils.get_workspace())
    services = controller.get_services(cli, project_key)
    tasks = [__ for _ in services.values() for __ in controller.inspect_service(_)['tasks']]
    return [_ for _ in (list(services.keys()) + tasks) if _.startswith(incomplete)]
