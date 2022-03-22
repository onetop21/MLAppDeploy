import traceback
from typing import List

from fastapi import APIRouter, Query, Header, HTTPException

from mlad.core import exceptions
from mlad.core.kubernetes import controller as ctlr
from mlad.service.exceptions import exception_detail
from mlad.service.libs.log import init_logger


router = APIRouter()
logger = init_logger(__name__)


@router.get("/node/list")
def node_list(session: str = Header(None)):
    try:
        nodes = ctlr.get_k8s_nodes()
        return [ctlr.inspect_k8s_node(node) for node in nodes]
    except Exception as e:
        logger.error(e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/node/resource")
def node_resource(names: List[str] = Query(None), no_trunc: bool = Query(True)):
    res = {}
    try:
        nodes = ctlr.get_k8s_nodes()
        if names is not None and len(names) > 0:
            nodes = [node for node in nodes if node.metadata.name in names]
        for node in nodes:
            resource = ctlr.get_k8s_node_resources(node, no_trunc)
            res[node.metadata.name] = resource
        return res
    except exceptions.NotFound as e:
        logger.error(e)
        raise HTTPException(status_code=400, detail=exception_detail(e))
    except Exception as e:
        logger.error(e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))
