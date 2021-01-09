from typing import Optional

from fastapi import FastAPI

app = FastAPI()

'''
# 인증 (Admin 전용)
POST    /api/v1/admin/user_token    * generate user token
GET     /api/v1/user/auth           * authenticate user token

# 설정 (Admin 전용)
POST    /api/v1/config          * create server config
PUT     /api/v1/config          * update server config
GET     /api/v1/config          * get server config

# 프로젝트
POST    /api/v1/project         create_project_network
GET     /api/v1/project         get_project_networks
GET     /api/v1/project/[ID]    inspect_project_network
DELETE  /api/v1/project/[ID]    remove_project_network

# 서비스 (컨트롤러에서 사용 가능)
POST    /api/v1/project/[ID]/service            create_services
GET     /api/v1/project/[ID]/service            get_services
GET     /api/v1/project/[ID]/service/[ID]       inspect_service
GET     /api/v1/project/[ID]/service/[ID]/tasks get_task_ids
PUT     /api/v1/project/[ID]/service/[ID]/scale scale_services
DELETE  /api/v1/project/[ID]/service/[ID]       remove_services

# 로그 (컨트롤러에서 사용 가능)
GET     /api/v1/project/[ID]/logs               * logs

# 이미지 (로컬에서 하는게 나을 수도 있음)
POST    /api/v1/image       build_image
GET     /api/v1/image       get_images
GET     /api/v1/image/[ID]  * inspect_image
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

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Optional[str] = None):
    return {"item_id": item_id, "q": q}
'''
/
/image_list
/image_build
/image_remove
/image_prune
/
'''
