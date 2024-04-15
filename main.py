from datetime import datetime, timedelta, timezone
from uuid import uuid4
from enum import Enum
from typing import Annotated, Optional, Union

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

def collection(collection: str):
    return database.data.get(collection) or {}

def fetch(collection_name: str, key: str):
    return collection(collection_name).get(key)

def find(collection_name: str, predicate):
    return next((item for item in collection(collection_name).values() if predicate(item)), None)

def insert(collection_name: str, key: str, value: BaseModel):
    if collection_name not in database.data:
        database.data[collection_name] = {}
    database.data[collection_name][key] = value.model_dump(mode='json')
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
    university: Optional[str]

class User(UserData):
    id: str

class UserPassword(User):
    hashed_password: str

def get_user_by_id(id: str):
    user_dict = fetch("users", id)
    if user_dict is not None:
        return User(**user_dict)
    
def assert_user_by_id(id: str):
    user = get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=400, detail=f"No user with the id '{id}' found") 
    return user

# potential improvement: increase the efficiency of this operation with a secondary index
def get_user_by_name(username: str):
    return find("users", lambda u: u["username"] == username)
    
def validate_user(user: User):
    existing_user_same_name = find("users", lambda u: u["username"] == user.username and u["id"] != user.id)
    if existing_user_same_name is not None:
        raise HTTPException(status_code=400, detail=f"User with name '{user.username}' already exists")
    if user.group != UserGroup.ADMIN and fetch("universities", user.university) is None:
        raise HTTPException(status_code=400, detail=f"Users of group '{user.group}' must be associated with an existing university")
    elif user.group == UserGroup.ADMIN and user.university is not None:
        raise HTTPException(status_code=400, detail=f"Admin users cannot be associated with a university")

## university

class UniversityData(BaseModel):
    name: str

class University(UniversityData):
    id: str

# potential improvement: increase the efficiency of this operation with a secondary index
def get_university_by_name(name: str):
    return find("universities", lambda u: u["name"] == name)

def validate_university(university: University):
    existing_university_same_name = find("universities", lambda u: u["name"] == university.name and u["id"] != university.id)
    if existing_university_same_name is not None:
        raise HTTPException(status_code=400, detail=f"University with name '{university.name}' already exists")

## room

class RoomData(BaseModel):
    university: str
    name: str

class Room(RoomData):
    id: str

def validate_room(room: Room):
    existing_room_same_name = find("rooms", lambda r: r["name"] == room.name and r["university"] == room.university and r["id"] != room.id)
    if existing_room_same_name is not None:
        raise HTTPException(status_code=400, detail=f"Room with name '{room.name}' already exists")
    university = fetch("universities", room.university)
    if university is None:
        raise HTTPException(status_code=400, detail=f"University with id '{room.university}' does not exist")

def fetch_owned_room(user: User, id: str):
    room = fetch("rooms", id)
    if room is None or (user.group != UserGroup.ADMIN and user.university != room.get("university")):
        raise HTTPException(status_code=400, detail=f"No room with the id '{id}' found")
    return Room(**room)

## time

class TimeData(BaseModel):
    start: datetime
    end: datetime

class RoomTimeData(TimeData):
    room: str

class Time(RoomTimeData):
    registrant: str
    id: str

def overlaps_with(self: Time, other: Time):
    if self.room != other.room:
        return False
    if self.start >= other.end:
        return False
    if self.end <= other.start:
        return False
    return True

def validate_time(time: Time):
    if time.start >= time.end:
        raise HTTPException(status_code=400, detail=f"Start must not be later than end")
    overlapping_time = find("times", lambda t: overlaps_with(time, Time(**t)))
    if overlapping_time is not None:
        overlapping_time = Time(**overlapping_time)
        raise HTTPException(status_code=400, detail=f"Time overlaps with existing scheduled time: {overlapping_time.start} to {overlapping_time.end}")

def fetch_owned_time(user: User, id: str):
    nonexistent = HTTPException(status_code=400, detail=f"No time with the id '{id}' found")
    time = fetch("times", id)
    if time is None:
        raise nonexistent
    time = Time(**time)
    room = fetch("rooms", time.room)
    if user.group != UserGroup.ADMIN and user.university != room.get("university"):
        raise nonexistent
    return time

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
    database.save()
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
    if new_user.password != new_user.password_confirmation:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    # no password security validation, not the focus of the project
    new_user_data = new_user.model_dump(exclude=["password", "password_confirmation"])
    user = User(id=id, **new_user_data)
    hashed_password = hash_password(new_user.password)
    database_user = UserPassword(hashed_password=hashed_password, **user.model_dump())
    return user, database_user

@app.post("/users/create")
async def users_create(current_user: Annotated[User, Depends(get_current_user)], new_user: NewUser):
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized

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
    rooms_to_delete = [room_id for room_id, room in collection("rooms").items() if room["university"] == university_id]
    for room_id in rooms_to_delete:
        delete_room(room_id, save=False)
    users_to_delete = [user_id for user_id, user in collection("users").items() if user["university"] == university_id]
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
    to_delete = [time_id for time_id, time in collection("times").items() if time["room"] == room_id]
    for time_id in to_delete:
        delete_time(time_id, save=False)
    if save:
      database.save()

class NewRoom(BaseModel):
    university: Optional[str] = None
    name: str

# this indirection is unfortunately necessary to allow `university`
# to be unspecified :(
# i'll leave it assymmetric with regards to how the other /create endpoints operate,
# as in theory i would like to eventually find a solution that removes this indirection,
# as opposed to introducing it to every other endpoint
class RoomCreate(BaseModel):
    room: NewRoom

@app.post("/rooms/create")
async def rooms_create(current_user: Annotated[User, Depends(get_current_user)], create: RoomCreate):
    if current_user.group == UserGroup.ADMIN:
        if create.room.university is None:
            raise HTTPException(status_code=400, detail=f"You must specify a university to create this room in")
    elif current_user.group == UserGroup.MANAGER:
        if create.room.university is not None:
            raise HTTPException(status_code=400, detail=f"You may not specify the university when creating a room")
        else:
            create.room.university = current_user.university 
    else:
        raise unauthorized
    
    id = str(uuid4())
    room_data = RoomData(**create.room.model_dump())
    room = Room(id=id, **room_data.model_dump())
    validate_room(room)
    insert("rooms", id, room)
    if current_user.group != UserGroup.ADMIN:
        room = UniversityRoom(**room.model_dump())
    return room

class UniversityRoom(BaseModel):
    id: str
    name: str

@app.get("/rooms/list")
async def rooms_list(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.group == UserGroup.ADMIN:
        return [Room(**room) for room in collection("rooms").values()]
    else:
        return [UniversityRoom(**room) for room in collection("rooms").values() if room["university"] == current_user.university]

class RoomUpdate(BaseModel):
    id: str
    data: NewRoom

@app.post("/rooms/update")
async def rooms_update(current_user: Annotated[User, Depends(get_current_user)], update: RoomUpdate):
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER]:
        raise unauthorized
    if current_user.group == UserGroup.MANAGER:
        if update.data.university is not None:
            raise HTTPException(status_code=400, detail=f"You may not change the university of an existing room")
    room = fetch_owned_room(current_user, update.id)
    
    if update.data.university is None:
      update.data.university = room.university
    room_data = RoomData(**update.data.model_dump())
    room = Room(id=update.id, **room_data.model_dump())
    validate_room(room)
    insert("rooms", update.id, room)
    if current_user.group != UserGroup.ADMIN:
        room = UniversityRoom(**room.model_dump())
    return room

class RoomDelete(BaseModel):
    id: str

@app.post("/rooms/delete")
async def rooms_delete(current_user: Annotated[User, Depends(get_current_user)], delete: RoomDelete):
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER]:
        raise unauthorized
    fetch_owned_room(current_user, delete.id)
    
    delete_room(delete.id)
    return { "success": True }

## times

def delete_time(time_id: str, save: bool = True):
    del database.data["times"][time_id]
    if save:
      database.save()

class TimeDataWithOptionalRegistrant(RoomTimeData):
    registrant: Optional[str] = None

@app.post("/times/create")
async def times_create(current_user: Annotated[User, Depends(get_current_user)], new_time: TimeDataWithOptionalRegistrant):
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER, UserGroup.PERSONNEL]:
        raise unauthorized
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER] and new_time.registrant is not None and new_time.registrant != current_user.id:
        raise HTTPException(status_code=400, detail=f"You may not register a new time under a different user")
    if new_time.registrant is None:
        new_time.registrant = current_user.id
    fetch_owned_room(current_user, new_time.room)

    id = str(uuid4())
    time = Time(id=id, **new_time.model_dump())
    validate_time(time)
    insert("times", id, time)
    return time

class ListTime(TimeData):
    registrant: str
    id: str

@app.get("/times/list")
async def times_list(current_user: Annotated[User, Depends(get_current_user)], room_id: str):
    fetch_owned_room(current_user, room_id)

    return [ListTime(**time) for time in collection("times").values() if time["room"] == room_id]

class TimeUpdate(BaseModel):
    id: str
    data: TimeDataWithOptionalRegistrant

@app.post("/times/update")
async def times_update(current_user: Annotated[User, Depends(get_current_user)], update: TimeUpdate):
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER, UserGroup.PERSONNEL]:
        raise unauthorized
    time = fetch_owned_time(current_user, update.id)
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER]:
        if time.registrant != current_user.id:
          raise HTTPException(status_code=400, detail=f"You may not change details of registered times you did not create")
        if update.data.registrant is not None and update.data.registrant != current_user.id:
          raise HTTPException(status_code=400, detail=f"You may not change the registrant of your own time")
    
    if update.data.registrant is None:
        update.data.registrant = time.registrant
    new_time = Time(id=time.id, **update.data.model_dump())
    validate_time(new_time)
    insert("times", time.id, new_time)
    return new_time

class TimeDelete(BaseModel):
    id: str

@app.post("/times/delete")
async def rooms_delete(current_user: Annotated[User, Depends(get_current_user)], delete: TimeDelete):
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER, UserGroup.PERSONNEL]:
        raise unauthorized
    time = fetch_owned_time(current_user, delete.id)
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER] and time.registrant != current_user.id:
        raise HTTPException(status_code=400, detail=f"You may not delete registered times you did not create")
    
    delete_time(time.id)
    return { "success": True }

# potential enhancements:
# * allow deletion of a range of times between a start and end time
# * allow variadic specification of fields to modify in `update` requests