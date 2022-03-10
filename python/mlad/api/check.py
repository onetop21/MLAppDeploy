from typing import Optional

from .base import APIBase


class Check(APIBase):
    def __init__(self, address: Optional[str], session: Optional[str]):
        super().__init__(address, session, 'check')

    def check_metrics_server(self):
        return self._get('/metrics-server')

    def check_nvidia_device_plugin(self):
        return self._get('/nvidia-device-plugin')

    def check_ingress_controller(self):
        return self._get('/ingress-controller')
