from .base import APIBase


class Check(APIBase):
    def __init__(self, config):
        super().__init__(config, 'check')

    def check_metrics_server(self):
        return self._get('/metrics-server')

    def check_nvidia_device_plugin(self):
        return self._get('/nvidia-device-plugin')

    def check_ingress_controller(self):
        return self._get('/ingress-controller')
