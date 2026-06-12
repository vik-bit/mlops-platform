from fastapi import HTTPException
from fastapi import Request


def require_admin(request: Request):

    user = request.state.user

    if user.get("role") != "admin":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )


def require_roles(
    request: Request,
    roles: list
):

    user = request.state.user

    if user.get("role") not in roles:

        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )