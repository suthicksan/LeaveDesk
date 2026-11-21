from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.core.security import verify_password, create_access_token
from app.core.auth import get_current_user
from app.schemas.auth import UserResponse
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    # Find the user using their email address
    user = db.scalar(
        select(User).where(User.email == login_data.email)
    )

    # Return the same error for an unknown email or wrong password
    if user is None or not verify_password(
        login_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Generate JWT using the user's database ID
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )

    # Return the token to the client
    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )

@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user

