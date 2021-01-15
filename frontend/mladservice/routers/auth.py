from typing import List
from fastapi import APIRouter, Query, Header, HTTPException
from mladservice.models.auth import TokenRequest
from mladcli.libs.auth import generate_user_token, decode_token, verify_token

router = APIRouter()

@router.post("/admin/user_token")
def create_token(req: TokenRequest):
    username = req.username
    user_token = generate_user_token(username)
    return {'token': user_token}

# @router.get("/user/auth")
# def verify_token(token: str = Header(None)):
#     decoded = decode_token(token) #user token
#     print(decoded)
#     res = verify_token(decoded)
#     return {'result': res}
