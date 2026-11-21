
from pydantic import BaseModel, ConfigDict, Field


# Data received during login (Receives email and password)
class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


# Data returned after successful login (Returns the JWT after login)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Public user information returned by the API (Returns safe user information)
class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    manager_id: int | None

    # Allow Pydantic to read values from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)