from mlad.core.docker import controller as ctlr
from mlad.cli import board, config
from mlad.api import API


def list_project_keys(ctx, args, incomplete):
    project_specs = API.project.get()
    keys = [spec['key'] for spec in project_specs]
    return [key for key in keys if key.startswith(incomplete)]


def list_component_names(ctx, args, incomplete):
    containers = board.list(no_print=True)
    component_names = set([container.labels['COMPONENT_NAME']
                          for container in containers])
    return [name for name in component_names if name.startswith(incomplete)]


def list_config_names(ctx, args, incomplete):
    spec = config._load()
    names = [conf.name for conf in spec.configs]
    return [name for name in names if name.startswith(incomplete)]


def list_image_ids(ctx, args, incomplete):
    specs = [ctlr.inspect_image(image) for image in ctlr.get_images()]
    ids = [spec['short_id'] for spec in specs]
    return [_id for _id in ids if _id.startswith(incomplete)]


def list_node_names(ctx, args, incomplete):
    nodes = API.node.list()
    return [node['hostname'] for node in nodes if node['hostname'].startswith(incomplete)]
