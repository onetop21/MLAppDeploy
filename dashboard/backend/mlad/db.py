import os

from typing import List, Dict
from pymongo import MongoClient
from .model import ComponentPostModel


# os.environ['DB_ADDRESS'] = 'mongodb://172.20.41.35:27017'


class DBClient:
    '''
    Component 설치에 관한 메타데이터를 관리하기 위한 client
    '''
    def __init__(self):
        self.client = MongoClient(self._get_url())

    def _get_url(self):
        address = os.environ['DB_ADDRESS']
        username = os.environ.get('DB_USERNAME', '')
        password = os.environ.get('DB_PASSWORD', '')
        if username != '' and password != '':
            address = address[len('mongodb://'):] \
                if address.startswith('mongodb://') else address
            address = f'mongodb://{username}:{password}@{address}'
        return address

    def get_components(self) -> List[Dict]:
        return list(self.client['mlad-board'].components.find({}, {'_id': 0}))

    def run_component(self, components: List[ComponentPostModel]) -> None:
        self.client['mlad-board'].components.insert_many([c.dict() for c in components])

    def delete_component(self, name: str) -> None:
        if name == 'mlad-board':
            self.client['mlad-board'].components.delete_many({})
        else:
            self.client['mlad-board'].components.delete_one({'name': name})
