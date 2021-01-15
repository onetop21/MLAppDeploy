from typing import List
from fastapi import APIRouter, Query, Header, HTTPException
from mladservice.models.auth import TokenRequest
from mladcli.libs.auth import generate_user_token, decode_token, verify_token

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
        return {'result': res, 'data': decoded}
    else:
        return {'result': res}
