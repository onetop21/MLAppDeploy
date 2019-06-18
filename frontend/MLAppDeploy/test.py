import sys, os
from pathlib import Path
import MLAppDeploy.utils as utils
import MLAppDeploy.default as default

def module(no_build):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    print('Generating container image for test...')
    utils.convert_dockerfile(project['project'], project['workspace'])
    project_name, image_name = utils.generate_image(project['project'], project['workspace'], True)

    print('Deploying test container image to local...')
    utils.start_project(project_name, image_name, project['services'], True)

    utils.show_project_logs(project_name, True)

    #utils.networks.prune()

    utils.stop_project(project_name, True)

    print('Done.')

sys.modules[__name__] = module
