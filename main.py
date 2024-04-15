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

# data model

class UserGroup(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    PERSONNEL = "personnel"
    USER = "user"

class UserData(BaseModel):
    username: str
    group: UserGroup
    university: Union[str, None]

class User(UserData):
    id: str

class UserPassword(User):
    hashed_password: str

class UniversityData(BaseModel):
    name: str

class University(UniversityData):
    id: str

class RoomData(BaseModel):
    university_id: str
    name: str

class Room(RoomData):
    id: str

class TimeData(BaseModel):
    room_id: str
    start: datetime
    end: datetime

class Time(TimeData):
    id: str

# user authentication

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

@app.get("/user/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

class HashForm(BaseModel):
    password: str

@app.post("/hash")
async def hash(hash_form: HashForm):
    return { "hashed_password": hash_password(hash_form.password) }

# CRUD operations

## user

class NewUser(UserData):
    password: str
    password_confirmation: str

@app.post("/users/create")
async def users_create(current_user: Annotated[User, Depends(get_current_user)], new_user: NewUser):
    pass

@app.get("/users/list")
async def users_list(current_user: Annotated[User, Depends(get_current_user)]):
    pass

@app.post("/users/update")
async def users_update(current_user: Annotated[User, Depends(get_current_user)], user_id: str, user_data: NewUser):
    pass

@app.post("/users/delete")
async def users_delete(current_user: Annotated[User, Depends(get_current_user)], user_id: str):
    pass

## universities

@app.post("/universities/create")
async def universities_create(current_user: Annotated[User, Depends(get_current_user)], new_university: UniversityData):
    pass

@app.post("/universities/list")
async def universities_list(current_user: Annotated[User, Depends(get_current_user)]):
    pass

@app.post("/universities/update")
async def universities_update(current_user: Annotated[User, Depends(get_current_user)], university_id: str, university_data: UniversityData):
    pass

@app.post("/universities/delete")
async def universities_delete(current_user: Annotated[User, Depends(get_current_user)], university_id: str):
    pass

## rooms

@app.post("/rooms/create")
async def rooms_create(current_user: Annotated[User, Depends(get_current_user)], new_room: RoomData):
    pass

@app.post("/rooms/list")
async def rooms_list(current_user: Annotated[User, Depends(get_current_user)]):
    pass

@app.post("/rooms/update")
async def rooms_update(current_user: Annotated[User, Depends(get_current_user)], room_id: str, room_data: RoomData):
    pass

@app.post("/rooms/delete")
async def rooms_delete(current_user: Annotated[User, Depends(get_current_user)], room_id: str):
    pass

## times

@app.post("/times/create")
async def times_create(current_user: Annotated[User, Depends(get_current_user)], new_time: TimeData):
    pass

@app.post("/times/list")
async def times_list(current_user: Annotated[User, Depends(get_current_user)], room_id: str):
    pass

@app.post("/times/update")
async def times_update(current_user: Annotated[User, Depends(get_current_user)], time_id: str, time_data: TimeData):
    pass

@app.post("/times/delete")
async def rooms_delete(current_user: Annotated[User, Depends(get_current_user)], time_id: str):
    pass