import os
import uvicorn
from mlad import __version__
from mlad.service.libs import utils

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mlad.service.routers import service, project, node
from mlad.core.default.config import service_config

'''
# 인증 (Admin 전용)
POST    /api/v1/admin/user_token    generate_user_token
GET     /api/v1/user/auth           verify_token(decode_token())

# 설정 (Admin 전용) -> docker config 사용하는 것으로?
#POST    /api/v1/config          * create server config
#PUT     /api/v1/config          * update server config
GET     /api/v1/config          * get server config

# 프로젝트
POST    /api/v1/project         create_project_network
GET     /api/v1/project         get_project_networks
GET     /api/v1/project/[PID]   inspect_project_network
DELETE  /api/v1/project/[PID]   remove_project_network

# 서비스 (컨트롤러에서 사용 가능)
POST    /api/v1/project/[PID]/service               create_services
GET     /api/v1/project/[PID]/service               get_services
GET     /api/v1/project/[PID]/service/[SID]         inspect_service
GET     /api/v1/project/[PID]/service/[SID]/tasks   inspect_service(get_service())['tasks']
PUT     /api/v1/project/[PID]/service/[SID]/scale   scale_services
DELETE  /api/v1/project/[PID]/service/[SID]         remove_services

# 로그 (컨트롤러에서 사용 가능)
GET     /api/v1/project/[ID]/logs               * logs

# 이미지 (로컬에서 하는게 나을 수도 있음)
POST    /api/v1/image       build_image
GET     /api/v1/image       get_images
GET     /api/v1/image/[ID]  inspect_image
DELETE  /api/v1/image/[ID]  remove_image
DELETE  /api/v1/image       prune_images
POST    /api/v1/image       push_images

# 노드 (Admin 전용)
GET     /api/v1/node                get_nodes
GET     /api/v1/node/[ID]           inspect_node
PUT     /api/v1/node/[ID]/state     enable_node
PUT     /api/v1/node/[ID]/state     disable_node
POST    /api/v1/node/[ID]/labels    add_node_labels
DELETE  /api/v1/node/[ID]/labels    remove_node_labels
'''

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
    app.include_router(service.router, prefix=APIV1)
    app.include_router(project.router, prefix=APIV1)

    #print(f"Admin Token  : {generate_admin_token().decode()}")
    print("Orchestrator : 'Kubernetes'")
    print(f"Debug        : {'TRUE' if utils.is_debug_mode() else 'FALSE'}")
    print(f'Prefix       : {root_path}')
    return app


app = create_app()


if __name__ == '__main__':
    uvicorn.run(app, host=service_config['server']['host'],
                port=service_config['server']['port'],
                debug=service_config['server']['debug'])
