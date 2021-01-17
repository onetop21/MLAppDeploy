from fastapi import APIRouter, HTTPException
from mlad.service.models import node
from mlad.core.docker import controller as ctlr

router = APIRouter()

@router.get("/node/list")
def node_list():
    cli = ctlr.get_docker_client()
    try:
        nodes = ctlr.get_nodes(cli)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return list(nodes.keys())

@router.get("/node/{node_id}")
def node_inspect(node_id:str):
    cli = ctlr.get_docker_client()
    try:
        node = ctlr.get_node(cli, node_id)
        inspects = ctlr.inspect_node(node)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspects

@router.post("/node/{node_id}/enable")
def node_enable(node_id:str):
    cli = ctlr.get_docker_client()
    try:
        ctlr.enable_node(cli, node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message': f'{node_id} enabled'}

@router.post("/node/{node_id}/disable")
def node_disable(node_id:str):
    cli = ctlr.get_docker_client()
    try:
        ctlr.disable_node(cli, node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    
    return {'message': f'{node_id} disabled'}

@router.post("/node/{node_id}/labels")
def node_add_label(node_id:str, req:node.AddLabelRequest):
    cli = ctlr.get_docker_client()
    try:
        ctlr.add_node_labels(cli, node_id, **req.labels)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  
    return {'message': 'labels added'}

@router.delete("/node/{node_id}/labels")
def node_delete_label(node_id:str, req:node.DeleteLabelRequest):
    cli = ctlr.get_docker_client()
    try:
        ctlr.remove_node_labels(cli, node_id, *req.keys)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message': 'labels deleted'}