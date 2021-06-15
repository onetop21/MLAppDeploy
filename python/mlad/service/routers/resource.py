from fastapi import APIRouter, HTTPException
from mlad.core import exception
from requests.exceptions import HTTPError
from mlad.service.libs.log import init_logger
from mlad.service.libs import utils
if not utils.is_kube_mode():
    from mlad.core.docker import controller as ctlr
else:
    from mlad.core.kubernetes import controller as ctlr


admin_router = APIRouter()
user_router = APIRouter()

logger = init_logger(__name__)

@admin_router.get("/resource/node")
def resource_nodes():
    cli = ctlr.get_api_client()
    res={}
    try:
        nodes = ctlr.get_nodes(cli)
        for node in nodes:
            name = node.metadata.name
            resource = ctlr.get_node_resources(node)
            res[name] = resource
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return res

@user_router.get("/resource/node/{node_name}")
def resource_node(node_name:str):
    cli = ctlr.get_api_client()
    try:
        node = ctlr.get_node(cli, node_name)
        resource = ctlr.get_node_resources(node)
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return resource
