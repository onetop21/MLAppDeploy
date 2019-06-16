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
    utils.convert_dockerfile(project['project'], project['workspace'])
    utils.convert_composefile(project['project'], project['services'])

sys.modules[__name__] = module
