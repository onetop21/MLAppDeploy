from typing import List
from fastapi import APIRouter, Query, HTTPException
from mlad.service.models import image
from mlad.service.libs import utils
from mlad.core.kubernetes import controller as ctlr

router = APIRouter()

@router.get("/image/list")
def image_list(project_key:str = Query(None)):
    cli = ctlr.get_api_client()
    try:
        images = ctlr.get_images(cli, project_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [image.short_id for image in images]

@router.get("/image/{image_id}")
def image_inspect(image_id:str):
    cli = ctlr.get_api_client()
    try:
        image = get_images(cli,image_id)
        inspect = ctlr.inspect(image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspect

@router.post("/image/build")    
def image_build():
    pass

@router.post("/image/push") 
def image_push():
    pass

@router.delete("/image/remove/{image_id}")
def image_remove(image_id:str, force:bool = Query(False)):
    cli = ctlr.get_api_client()
    try:
        ctlr.remove_image(cli, list(image_id), force)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message':'image removed'}

@router.delete("/image/prune")
def image_prune(project_key:str = Query(None)):
    cli = ctlr.get_api_client()
    try:
        res = ctlr.prune_images(cli, project_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return res