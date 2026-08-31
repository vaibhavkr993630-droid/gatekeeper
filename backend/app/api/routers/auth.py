from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbDep
from app.core.security import create_access_token, hash_password, verify_password
from app.crud import tenant as crud_tenant
from app.schemas.auth import LoginRequest, RegisterRequest, TenantUserOut, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DbDep) -> Token:
    if await crud_tenant.get_user_by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = await crud_tenant.create_tenant_with_owner(
        db,
        tenant_name=body.tenant_name,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    return Token(access_token=create_access_token(user_id=user.id, tenant_id=user.tenant_id))


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: DbDep) -> Token:
    user = await crud_tenant.get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return Token(access_token=create_access_token(user_id=user.id, tenant_id=user.tenant_id))


@router.get("/me", response_model=TenantUserOut)
async def me(current_user: CurrentUser) -> TenantUserOut:
    return current_user
