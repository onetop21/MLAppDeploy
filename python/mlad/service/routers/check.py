import traceback

from fastapi import APIRouter, HTTPException

from mlad.core import exceptions
from mlad.core.kubernetes import controller as ctlr
from mlad.service.exceptions import exception_detail


router = APIRouter()


@router.get("/check/metrics-server")
def check_metrics_server():
    status = True
    try:
        ctlr.get_deployment('metrics-server', 'kube-system')
    except exceptions.NotFound:
        status = False
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return status


@router.get("/check/nvidia-device-plugin")
def check_nvidia_device_plugin():
    status = True
    try:
        ctlr.get_daemonset('nvidia-device-plugin-daemonset', 'kube-system')
    except exceptions.NotFound:
        status = False
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return status
