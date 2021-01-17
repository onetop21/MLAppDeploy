import os
import uvicorn
#from mlad.service.main import app

from fastapi import FastAPI, Depends, Header
from fastapi.logger import logger
from fastapi import FastAPI, Depends
from mlad.service.routers import image, service, project, node, auth
from mlad.service.auth import Authorization
from mlad.service.libs.auth import generate_admin_token

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
    app = FastAPI()

    user = Authorization('user')
    admin = Authorization('admin')

    #app.include_router(image.router, prefix=APIV1)
    app.include_router(node.router,prefix=APIV1,
                       dependencies=[Depends(admin.verify_auth)])
    app.include_router(service.router, prefix=APIV1)
    app.include_router(project.router, prefix=APIV1,
                       dependencies=[Depends(user.verify_auth)])
    app.include_router(auth.admin_router, prefix=APIV1,
                       dependencies=[Depends(admin.verify_auth)])
    app.include_router(auth.user_router, prefix=APIV1)

    print(f"Admin Token : {generate_admin_token().decode()}")

    return app

app = create_app()

# Run by 'mlad-service # Not support yet'
def main():
    uvicorn.run(app, host=os.environ.get('HOST', '0.0.0.0'), port=os.environ.get('PORT', 2380))

# Run by 'python -m mlad.service'
if __name__ == '__main__':
    main()
