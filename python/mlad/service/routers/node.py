from typing import List
from fastapi import APIRouter, Query, HTTPException
from mlad.service.models import node
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

@admin_router.get("/node")
def node_list():
    cli = ctlr.get_api_client()
    try:
        nodes = ctlr.get_nodes(cli)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return list(nodes.keys())

@user_router.get("/node/{node_id}")
def node_inspect(node_id:str):
    cli = ctlr.get_api_client()
    try:
        node = ctlr.get_node(cli, node_id)
        inspects = ctlr.inspect_node(node)
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return inspects

@admin_router.post("/node/{node_id}/enable")
def node_enable(node_id:str):
    cli = ctlr.get_api_client()
    try:
        ctlr.enable_node(cli, node_id)
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'message': f'{node_id} enabled'}

@admin_router.post("/node/{node_id}/disable")
def node_disable(node_id:str):
    cli = ctlr.get_api_client()
    try:
        ctlr.disable_node(cli, node_id)
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'message': f'{node_id} disabled'}

@admin_router.post("/node/{node_id}/labels")
def node_add_label(node_id:str, req:node.AddLabelRequest):
    cli = ctlr.get_api_client()
    try:
        ctlr.add_node_labels(cli, node_id, **req.labels)
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'message': 'labels added'}

@admin_router.delete("/node/{node_id}/labels")
def node_delete_label(node_id:str, req:node.DeleteLabelRequest):
    cli = ctlr.get_api_client()
    try:
        ctlr.remove_node_labels(cli, node_id, *req.keys)
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'message': 'labels deleted'}

@admin_router.get("/node/resource")
def resource_nodes(nodes: List[str] = Query(None)):
    cli = ctlr.get_api_client()
    res={}
    try:
        if not nodes:
            nodes = ctlr.get_nodes(cli)
        for node in nodes:
            node = ctlr.get_node(cli, node)
            name = node.metadata.name
            resource = ctlr.get_node_resources(cli, node)
            res[name] = resource
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=400, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return res