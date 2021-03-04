from typing import List
from fastapi import APIRouter, Query, Header, HTTPException
from mlad.service.models.auth import TokenRequest
from mlad.service.libs.auth import generate_user_token
from mlad.service.libs.auth import decode_token, verify_token

admin_router = APIRouter()
user_router = APIRouter()

@admin_router.post("/admin/user_token")
def create_token(req: TokenRequest):
    username = req.username
    user_token = generate_user_token(username)
    return {'token': user_token}

@user_router.get("/user/auth")
def verify_user(user_token: str = Header(...)):
    decoded = decode_token(user_token)
    res = verify_token(decoded)
    if res:
        del decoded['hash_key']
        return {'result': res, 'data': decoded}
    else:
        return {'result': res}