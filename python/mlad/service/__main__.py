import os
import uvicorn
from mlad import __version__
from mlad.service.libs import utils

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mlad.service.exceptions import VersionCompatabilityError
from mlad.service.routers import app as app_router, project, node, check
from mlad.core.default.config import service_config


APIV1 = '/api/v1'


def create_app():
    root_path = os.environ.get('ROOT_PATH', '')
    app = FastAPI(
        title="MLAppDeploy API Server",
        description="MLAppDeploy is a tool for training "
                    "and deploying ML code easily.",
        version=__version__,
        root_path=root_path,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    app.include_router(node.router, prefix=APIV1)
    app.include_router(app_router.router, prefix=APIV1)
    app.include_router(project.router, prefix=APIV1)
    app.include_router(check.router, prefix=APIV1)

    print("Orchestrator : 'Kubernetes'")
    print(f"Debug        : {'TRUE' if utils.is_debug_mode() else 'FALSE'}")
    print(f'Prefix       : {root_path}')
    return app


app = create_app()


@app.middleware('http')
async def check_version(request: Request, call_next):
    client_version = request.headers.get('version', '0.3.1')
    server_version = __version__
    client_major, client_minor, client_patch = client_version.split('.', 2)
    server_major, server_minor, server_patch = server_version.split('.', 2)
    if client_major != server_major or client_minor != server_minor:
        raise VersionCompatabilityError(client_version, server_version)
    return await call_next(request)


if __name__ == '__main__':
    uvicorn.run(app, host=service_config['server']['host'],
                port=service_config['server']['port'],
                debug=service_config['server']['debug'])
