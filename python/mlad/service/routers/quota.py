import traceback

from fastapi import APIRouter, HTTPException

from mlad.core.kubernetes import controller as ctlr
from mlad.service.models.quota import SetDefaultRequest, SetRequest
from mlad.service.exceptions import exception_detail
from mlad.service.libs.log import init_logger


router = APIRouter(prefix='/quota')
logger = init_logger(__name__)


@router.post('/set_default')
def set_default(req: SetDefaultRequest):
    try:
        ctlr.set_default_session_quota(req.cpu, req.gpu, req.mem)
    except Exception as e:
        logger.error(e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.post('/set')
def set_quota(req: SetRequest):
    try:
        ctlr.set_session_quota(req.session, req.cpu, req.gpu, req.mem)
    except Exception as e:
        logger.error(e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))
