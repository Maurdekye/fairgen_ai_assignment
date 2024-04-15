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

def insert(collection: str, key: str, value: BaseModel):
    database.data[collection][key] = value.model_dump()
    database.save()

secret_key = "CHANGEME_7ca47b62f5463f69baddaeed7e528cd1b58cc121783c718a5096186a06e7b08c"
token_expire = 30
jwt_algorithm = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

unauthorized = HTTPException(status_code=401, detail="Unauthorized")

# data model

## user

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

def get_user_by_id(id: str):
    user_dict = database.data["users"].get(id)
    if user_dict is not None:
        return User(**user_dict)
    
def assert_user_by_id(id: str):
    user = get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=400, detail=f"No user with the id '{id}' found") 
    return user

# potential improvement: increase the efficiency of this operation with a secondary index
def get_user_by_name(username: str):
    return next((u for u in database.data["users"].values() if u["username"] == username), None)
    
def validate_user(user: User):
    existing_user_same_name = next((u for u in database.data["users"].values() if u["username"] == user.username and u["id"] != user.id), None)
    if existing_user_same_name is not None:
        raise HTTPException(status_code=400, detail=f"User with name '{user.username}' already exists")
    if user.group != UserGroup.ADMIN:
        if not user.university in database.data["universities"]:
            raise HTTPException(status_code=400, detail=f"Users of group '{user.group}' must be associated with a university")

## university

class UniversityData(BaseModel):
    name: str

class University(UniversityData):
    id: str

# potential improvement: increase the efficiency of this operation with a secondary index
def get_university_by_name(name: str):
    return next((u for u in database.data["universities"].values() if u["name"] == name), None)

def validate_university(university: University):
    existing_university_same_name = next((u for u in database.data["universities"].values() if u["name"] == university.name and u["id"] != university.id), None)
    if existing_university_same_name is not None:
        raise HTTPException(status_code=400, detail=f"University with name '{university.name}' already exists")

## room

class RoomData(BaseModel):
    university: str
    name: str

class Room(RoomData):
    id: str

## time

class TimeData(BaseModel):
    room: str
    start: datetime
    end: datetime

class Time(TimeData):
    id: str

# user authentication

# note: bcrypt warning appears in console due to outdated bcrypt support in the
# passlib package
# `(trapped) error reading bcrypt version`
# `AttributeError: module 'bcrypt' has no attribute '__about__'`
# see https://github.com/pyca/bcrypt/issues/684 for relevant information
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str):
    return pwd_context.hash(password)

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
    user_dict = get_user_by_name(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserPassword(**user_dict)
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

# CRUD operations

## user

def delete_user(id: str, save: bool = True):
    del database.data["users"][id]
    if save:
      database.save()

class NewUser(UserData):
    password: str
    password_confirmation: str

def create_user_from_new_user(id: str, new_user: NewUser):
    new_user_data = new_user.model_dump(exclude=["password", "password_confirmation"])
    user = User(id=id, **new_user_data)
    hashed_password = hash_password(new_user.password)
    database_user = UserPassword(hashed_password=hashed_password, **user.model_dump())
    return user, database_user

@app.post("/users/create")
async def users_create(current_user: Annotated[User, Depends(get_current_user)], new_user: NewUser):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if new_user.password != new_user.password_confirmation:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user_id = str(uuid4())
    user, database_user = create_user_from_new_user(user_id, new_user)
    validate_user(user)
    insert("users", user_id, database_user)
    return user

@app.get("/users/list")
async def users_list(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    
    return [User(**user) for user in database.data["users"].values()]

class UserUpdate(BaseModel):
    id: str
    data: NewUser

# profile updating & password changing are the same operation, 
# for implementation simplicity (not the focus of the assignment)
@app.post("/users/update")
async def users_update(current_user: Annotated[User, Depends(get_current_user)], update: UserUpdate):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if update.user_data.password != update.user_data.password_confirmation:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    assert_user_by_id(update.id)
    
    user, database_user = create_user_from_new_user(update.id, update.user_data)
    validate_user(user)
    insert("users", update.id, database_user)
    return user

class UserDelete(BaseModel):
    id: str

@app.post("/users/delete")
async def users_delete(current_user: Annotated[User, Depends(get_current_user)], delete: UserDelete):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if current_user.id == delete.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own user account")
    assert_user_by_id(delete.id)
    
    delete_user(delete.id)
    return { "success": True }

## universities

def delete_university(university_id: str, save: bool = True):
    del database.data["universities"][university_id]
    rooms = database.data.get("rooms") or {}
    rooms_to_delete = [room_id for room_id, room in rooms.items() if room["university"] == university_id]
    for room_id in rooms_to_delete:
        delete_room(room_id, save=False)
    users = database.data.get("users") or {}
    users_to_delete = [user_id for user_id, user in users.items() if user["university"] == university_id]
    for user_id in users_to_delete:
        delete_user(user_id, save=False)
    if save:
      database.save()

@app.post("/universities/create")
async def universities_create(current_user: Annotated[User, Depends(get_current_user)], new_university: UniversityData):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    
    id = str(uuid4())
    university = University(id=id, **new_university.model_dump())
    validate_university(university)
    insert("universities", id, university)
    return university

@app.get("/universities/list")
async def universities_list(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    
    return [University(**university) for university in database.data["universities"].values()]

class UniversityUpdate(BaseModel):
    id: str
    data: UniversityData

@app.post("/universities/update")
async def universities_update(current_user: Annotated[User, Depends(get_current_user)], update: UniversityUpdate):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if update.id not in database.data["universities"]:
        raise HTTPException(status_code=400, detail=f"University with id '{update.id}' does not exist")
    
    university = University(id=update.id, **update.data.model_dump())
    validate_university(university)
    insert("universities", update.id, university)
    return university

class UniversityDelete(BaseModel):
    id: str

@app.post("/universities/delete")
async def universities_delete(current_user: Annotated[User, Depends(get_current_user)], delete: UniversityDelete):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if delete.id not in database.data["universities"]:
        raise HTTPException(status_code=400, detail=f"University with id '{delete.id}' does not exist")
    
    delete_university(delete.id)
    return { "success": True }

## rooms

def delete_room(room_id: str, save: bool = True):
    del database.data["rooms"][room_id]
    times = database.data.get("times") or {}
    to_delete = [time_id for time_id, time in times.items() if time["room"] == room_id]
    for time_id in to_delete:
        delete_time(time_id, save=False)
    if save:
      database.save()

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

def delete_time(time_id: str, save: bool = True):
    del database.data["times"][time_id]
    if save:
      database.save()

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