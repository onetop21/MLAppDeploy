import os
import json
import asyncio
import inspect
import aiohttp

from typing import Callable
from collections import defaultdict

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from .model import ComponentDeleteRequestModel, ComponentPostRequestModel
from .db import DBClient

# os.environ['MLAD_ADDRESS'] = 'http://172.20.41.35:30547/beta'
# os.environ['MLAD_ADDRESS'] = 'http://172.20.41.35:8441'
# os.environ['MLAD_SESSION'] = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiam9vb25ob2UiLCJob3N0bmFtZSI6Impvb29uaG9lLU1TLTdCMjMiLCJ1dWlkIjoiMmZjODk1ZTEtZDE2Zi00NTBiLWJkNmQtMTRiYzVmNjUwZjhkIn0.HAaCZEaXMe9mZ1hDUaMMnu5u5mxMRvhLJhlD5cnX7HI'

app = FastAPI()
address = f'{os.environ["MLAD_ADDRESS"]}/api/v1'
headers = {
    'session': os.environ['MLAD_SESSION']
}
db_client = DBClient()


async def _request_resources(key: str, session: aiohttp.ClientSession):
    total_cpu = 0
    total_gpu = 0
    total_mem = 0
    resources = {}
    async with session.get(f'{address}/project/{key}/resource', headers=headers) as resp:
        resp.raise_for_status()
        resources = await resp.json()
    for tasks in resources.values():
        for resource in tasks.values():
            cpu = resource['cpu']
            total_cpu += cpu if cpu is not None else 0
            resource['cpu'] = cpu
            gpu = resource['gpu']
            total_gpu += gpu if gpu is not None else 0
            resource['gpu'] = gpu
            mem = resource['mem']
            total_mem += mem if mem is not None else 0
            resource['mem'] = mem
    return {'cpu': total_cpu, 'gpu': total_gpu, 'mem': total_mem}, resources


async def request_nodes(_, session: aiohttp.ClientSession):
    ret = []
    nodes = []
    async with session.get(f'{address}/node/list', headers=headers) as resp:
        resp.raise_for_status()
        nodes = await resp.json()

    resource_dict = defaultdict(lambda: {})
    async with session.get(f'{address}/node/resource', headers=headers) as resp:
        resp.raise_for_status()
        resource_dict = await resp.json()
    for node in nodes:
        name = node['hostname']
        ret.append({
            **node,
            'metrics': [{
                'type': k,
                'capacity': v['capacity'],
                'used': v['used'],
                'free': v['allocatable']
            } for k, v in resource_dict[name].items()]
        })
    return ret


async def request_projects(_, session: aiohttp.ClientSession):
    ret = []
    projects = []
    async with session.get(f'{address}/project', headers=headers) as resp:
        resp.raise_for_status()
        projects = await resp.json()

    async def fetch_apps(project):
        async with session.get(f'{address}/project/{project["key"]}/app', headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    apps_list = await asyncio.gather(*[fetch_apps(project) for project in projects])
    resource_res_coroutines = [
        _request_resources(project["key"], session)
        for project in projects
    ]
    resource_responses = await asyncio.gather(*resource_res_coroutines)
    for i, project in enumerate(projects):
        key = project['key']
        username = project['username']
        name = project['project']
        image = project['image']
        n_apps = 0
        n_replicas = 0
        n_tasks = 0
        hostname = project['workspace']['hostname']
        workspace = project['workspace']['path']
        apps = apps_list[i]
        for spec in apps['specs']:
            tasks = spec['tasks'].values()
            states = [t['status']['state'] for t in tasks]
            n_apps += 1
            n_replicas += spec['replicas']
            n_tasks += states.count('Running')

        total_resource, _ = resource_responses[i]
        ret.append({
            'key': key, 'username': username, 'name': name, 'image': image,
            'n_apps': n_apps, 'n_replicas': n_replicas, 'n_tasks': n_tasks,
            'hostname': hostname, 'workspace': workspace,
            **total_resource
        })
    return ret


def get_components(_):
    return db_client.get_components()


async def request_project_detail(data: str, session: aiohttp.ClientSession):
    data = json.loads(data)
    if len(data) == 0:
        return {}
    key = data['key']
    ret = {}
    async with session.get(f'{address}/project/{key}') as resp:
        resp.raise_for_status()
        ret = await resp.json()
    total_resource, resources = await _request_resources(key, session)
    ret = {**ret, **total_resource}

    specs = []
    async with session.get(f'{address}/project/{key}/app') as resp:
        resp.raise_for_status()
        apps = await resp.json()
        specs = apps['specs']
        for i, spec in enumerate(specs):
            specs[i] = {**specs[i], 'resources': resources[spec['name']]}

    ret = {**ret, 'apps': specs}
    return ret


@app.post('/component')
def run_components(req: ComponentPostRequestModel):
    db_client.run_component(req.components)
    return {
        'message': 'Successfully run components'
    }


@app.delete('/component')
def delete_components(req: ComponentDeleteRequestModel):
    db_client.delete_component(req.name)
    return {
        'message': f'Successfully delete component [{req.name}]'
    }


async def handle_message(websocket: WebSocket, request_func: Callable):
    await websocket.accept()
    while True:
        async with aiohttp.ClientSession() as session:
            try:
                data = await websocket.receive_text()
                if inspect.iscoroutinefunction(request_func):
                    ret = await request_func(data, session)
                else:
                    loop = asyncio.get_event_loop()
                    ret = await loop.run_in_executor(None, request_func, data)
                await websocket.send_json({'status_code': 200, 'data': ret})
            except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError, RuntimeError):
                pass
            except Exception as e:
                await websocket.send_json({'status_code': 500, 'message': str(e)})


@app.websocket('/nodes')
async def send_nodes(websocket: WebSocket):
    await handle_message(websocket, request_nodes)


@app.websocket('/components')
async def send_components(websocket: WebSocket):
    await handle_message(websocket, get_components)


@app.websocket('/projects')
async def send_projects(websocket: WebSocket):
    await handle_message(websocket, request_projects)


@app.websocket('/project')
async def send_project_detail(websocket: WebSocket):
    await handle_message(websocket, request_project_detail)