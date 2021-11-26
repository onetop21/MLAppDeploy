from mlad.core.docker import controller as ctlr
from mlad.cli import board, context
from mlad.api import API


def list_project_keys(ctx, args, incomplete):
    project_specs = API.project.get()
    keys = [spec['key'] for spec in project_specs]
    return [key for key in keys if key.startswith(incomplete)]


def list_component_names(ctx, args, incomplete):
    containers = board.list()
    component_names = set([container.labels['COMPONENT_NAME']
                          for container in containers])
    return [name for name in component_names if name.startswith(incomplete)]


def list_context_names(ctx, args, incomplete):
    config = context._load()
    names = [context.name for context in config.contexts]
    return [name for name in names if name.startswith(incomplete)]


def list_image_ids(ctx, args, incomplete):
    specs = [ctlr.inspect_image(image) for image in ctlr.get_images()]
    ids = [spec['short_id'] for spec in specs]
    return [_id for _id in ids if _id.startswith(incomplete)]


# def get_project_file_completion(ctx, args, incomplete):
#     files = glob.glob(f"{incomplete}*" or '*')
#     subcommands = [f"{_}/" for _ in files if os.path.isdir(_)]
#     subcommands += [_ for _ in files if _.endswith('.yaml') or _.endswith('.yml')]
#     return subcommands


# def get_dir_completion(ctx, args, incomplete):
#     files = glob.glob(f"{incomplete}*" or '*')
#     subcommands = [f"{_}/" for _ in files if os.path.isdir(_)]
#     return subcommands


# def get_node_list_completion(ctx, args, incomplete):
#     config = config_core.get()
#     try:
#         with API(config.apiserver.address, config.session) as api:
#             nodes = [api.node.inspect(_) for _ in api.node.get()]
#     except APIError as e:
#         print(e)
#         sys.exit(1)
#     hostnames = [_['hostname'] for _ in nodes]
#     ids = [_['id'][:ctlr.SHORT_LEN] for _ in nodes] if incomplete else []
#     return [_ for _ in hostnames + ids if _.startswith(incomplete)]


# def get_node_label_completion(ctx, args, incomplete):
#     config = config_core.get()
#     node_key = args[args.index('label') + 1]
#     try:
#         with API(config.apiserver.address, config.session) as api:
#             node = api.node.inspect(node_key)
#     except APIError as e:
#         print(e)
#         sys.exit(1)
#     keys = [f'{key}' for key, value in node['labels'].items()]
#     return [_ for _ in keys if _.startswith(incomplete)]


# def get_config_key_completion(ctx, args, incomplete):
#     config = OmegaConf.to_container(config_core.get(), resolve=True)

#     def compose_keys(config, stack=[]):
#         keys = []
#         for k, v in config.items():
#             stack.append(k)
#             if isinstance(v, dict):
#                 keys += compose_keys(config[k], stack.copy())
#             else:
#                 keys.append('.'.join(stack))
#             stack.pop(-1)
#         return keys
#     return [_ for _ in compose_keys(config) if _.startswith(incomplete)]


# def get_image_list_completion(ctx, args, incomplete):
#     cli = ctlr.get_api_client()
#     images = ctlr.get_images(cli)
#     inspects = [ctlr.inspect_image(_) for _ in images]
#     repos = [f"{_['repository']}{':'+_['tag'] if _['tag'] else ''}" for _ in inspects]
#     if incomplete:
#         separated_repos = [__ for _ in repos for __ in _.split(':')]
#         ids = [_['short_id'] for _ in inspects]
#         return [_ for _ in set(separated_repos + ids) if _.startswith(incomplete)]
#     else:
#         return [_ for _ in repos if _.startswith(incomplete)]


# def get_stopped_services_completion(ctx, args, incomplete):
#     config = config_core.get()
#     project_file = [_ for _ in [args[i + 1] for i, _ in enumerate(args[:-1])
#                     if _ in ['-f', '--file']] if os.path.isfile(_)]
#     if project_file:
#         utils.apply_project_arguments(project_file[-1], None)
#     project = utils.get_project(default_project)
#     project_key = utils.workspace_key()
#     try:
#         with API(config.mlad.address, config.mlad.token.user) as api:
#             services = [_['name'] for _ in api.service.get(project_key)['inspects']]
#     except APIError as e:
#         print(e)
#         sys.exit(1)
#     return [_ for _ in project['services']
#             if _.startswith(incomplete) and _ not in services]


# def get_running_services_completion(ctx, args, incomplete):
#     config = config_core.get()
#     project_file = [_ for _ in [args[i + 1] for i, _ in enumerate(args[:-1])
#                     if _ in ['-f', '--file']] if os.path.isfile(_)]
#     if project_file:
#         utils.apply_project_arguments(project_file[-1], None)
#     project_key = utils.workspace_key()
#     try:
#         with API(config.apiserver.address, config.session) as api:
#             services = [_['name'] for _ in api.service.get(project_key)['inspects']]
#     except APIError as e:
#         print(e)
#         sys.exit(1)
#     return [_ for _ in services if _.startswith(incomplete)]


# def get_running_services_tasks_completion(ctx, args, incomplete):
#     config = config_core.get()
#     project_file = [_ for _ in [args[i + 1] for i, _ in enumerate(args[:-1])
#                     if _ in ['-f', '--file']] if os.path.isfile(_)]
#     if project_file:
#         utils.apply_project_arguments(project_file[-1], None)
#     project_key = utils.workspace_key()
#     try:
#         with API(config.apiserver.address, config.session) as api:
#             services = dict([(_['name'], _['tasks']) for _ in api.service.get(project_key)['inspects']])
#     except APIError as e:
#         print(e)
#         sys.exit(1)
#     tasks = [__ for _ in services.keys() for __ in services[_].keys()]
#     return [_ for _ in (list(services.keys()) + tasks) if _.startswith(incomplete)]
