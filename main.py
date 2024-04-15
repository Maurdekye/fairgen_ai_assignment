from datetime import datetime, timedelta, timezone
from uuid import uuid4
from enum import Enum
from typing import Annotated, Union

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext

from simplejsondb import Database

database = Database("database.json", default={
    "users": {},
    "universities": {},
    "rooms": {},
    "times": {},
})

secret_key = "CHANGEME_7ca47b62f5463f69baddaeed7e528cd1b58cc121783c718a5096186a06e7b08c"
token_expire = 30
jwt_algorithm = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserGroup(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    PERSONNEL = "personnel"
    USER = "user"

class User(BaseModel):
    id: str
    username: str
    group: UserGroup
    university: Union[str, None]

class UserPassword(User):
    hashed_password: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password):
    return pwd_context.hash(password)

def get_user_by_id(id):
    user_dict = database.data["users"].get(id)
    if user_dict is not None:
        return User(**user_dict)
    
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(status_code=400, detail="Invalid authentication credentials")
    try:
        payload = jwt.decode(token, secret_key, algorithms=[jwt_algorithm])
        id: str = payload.get("sub")
        if id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_id(id)
    if user is None:
        raise credentials_exception
    return user

@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    print(database.data)
    user_dict = next((u for u in database.data["users"].values() if u["username"] == form_data.username), None)
    print(user_dict)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserPassword(**user_dict)
    print(user)
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    expire = datetime.now(timezone.utc) + timedelta(minutes=token_expire)
    access_token = jwt.encode({"exp": expire, "sub": user.id }, secret_key, algorithm=jwt_algorithm)
    return { "access_token": access_token, "token_type": "bearer" }

@app.get("/users/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

class HashForm(BaseModel):
    password: str

@app.post("/hash")
async def hash(hash_form: HashForm):
    return { "hashed_password": hash_password(hash_form.password) }