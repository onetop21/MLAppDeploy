from typing import List
from fastapi import APIRouter, Query, Header, HTTPException
from mlad.service.models import node
from mlad.core import exception
from requests.exceptions import HTTPError
from mlad.service.exception import exception_detail
from mlad.service.libs.log import init_logger
from mlad.service.libs import utils
if not utils.is_kube_mode():
    from mlad.core.docker import controller as ctlr
else:
    from mlad.core.kubernetes import controller as ctlr


router = APIRouter()
logger = init_logger(__name__)


@router.get("/node")
def node_list(session: str = Header(None)):
    try:
        nodes = ctlr.get_nodes()
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return list(nodes.keys())


@router.get("/node/{node_id}")
def node_inspect(node_id:str, session: str = Header(None)):
    try:
        node = ctlr.get_node(node_id)
        inspects = ctlr.inspect_node(node)
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return inspects


@router.get("/nodes/resource")
def node_resource(nodes: List[str] = Query(None)):
    res={}
    try:
        if not nodes:
            nodes = ctlr.get_nodes()
        for node in nodes:
            node = ctlr.get_node(node)
            name = node.metadata.name
            resource = ctlr.get_node_resources(node)
            res[name] = resource
    except exception.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=400, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return res