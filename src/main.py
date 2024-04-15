from uuid import uuid4
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from model import Room, RoomData, RoomTimeData, Time, TimeData, University, UniversityData, User, UserData, UserGroup, UserPassword, assert_user_by_id, delete_room, delete_time, delete_university, delete_user, fetch_owned_room, fetch_owned_time, validate_room, validate_time, validate_university, validate_user
from authorization import get_access_token, get_current_user, hash_password
from database import collection, database, insert

app = FastAPI(
    title="Fairgen AI Assignment",
    description="""
This is an implementation of Fairgen AI's interview assignment. It is a basic REST api for the management of universities and university personnel. It also allows scheduling and reviewing times within rooms of the university to assist with class scheduling.
""",
    openapi_tags=[
        {
            "name": "authentication",
            "description": "Operations related to user authentication.",
        },
        {
            "name": "users",
            "description": "Operations on users and user accounts. Only `admin` accounts are authorized to make user account changes.",
        },
        {
            "name": "universities",
            "description": "Operations on universities. Only `admin` accounts are authorized to make updates to universities.",
        },
        {
            "name": "rooms",
            "description": "Operations on rooms within universities. `manager` accounts, which are associated with a university, may only create, update, and delete rooms within the university they belong to. `admin` accounts may perform operations on rooms belonging to any university. All users can list rooms for the university they belong to.",
        },
        {
            "name": "times",
            "description": "Operations on scheduled times within rooms. `manager` accounts may create, update, and delete any times for rooms within the university they belong to. `personnel` may create times in any room in the university they belong to, but may only update or delete times they themselves have created. `admin` accounts may perform operations on times belonging to any university. All accounts may list times for a room in the university they belong to",
        },
    ]
)

unauthorized = HTTPException(status_code=401, detail="Unauthorized")

# authorization

@app.post("/token", tags=["authentication"])
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Log in with a username and password via OAuth2.
    """
    return get_access_token(form_data)

@app.get("/users/me", tags=["authentication"])
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Get the current logged in user.
    """
    return current_user

class HashForm(BaseModel):
    password: str = Field(example="my-password")

# this is a bit of a hacky workaround to bootstrap creating an initial user account, 
# but other solutions involve much more in-depth work
@app.post("/hash", tags=["authentication"])
async def hash(hash_form: HashForm):
    """
    Hash a plaintext password. 
    
    Used for the account bootstrap process.
    """
    database.save() # save the empty database so it can be modified by the user
    return { "hashed_password": hash_password(hash_form.password) }

# CRUD operations

## user

class NewUser(UserData):
    password: str = Field(example="my-password")
    password_confirmation: str = Field(example="my-password")

def create_user_from_new_user(id: str, new_user: NewUser):
    if new_user.password != new_user.password_confirmation:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    # no password security validation, not the focus of the project
    new_user_data = new_user.model_dump(exclude=["password", "password_confirmation"])
    user = User(id=id, **new_user_data)
    hashed_password = hash_password(new_user.password)
    database_user = UserPassword(hashed_password=hashed_password, **user.model_dump())
    return user, database_user

@app.post("/users/create", tags=["users"])
async def users_create(current_user: Annotated[User, Depends(get_current_user)], new_user: NewUser):
    """
    Create a new user. 
    
    Only `admin` accounts may create new users; others are unauthorized.

    Newly created users must be part of one of four groups: `"admin"`, 
    `"manager"`, `"personnel"`, or `"user"`. All user account types except 
    for `"admin"` must be associated with a university, and must have the 
    `"university"` field set to the id of an existing university. `"admin"` 
    accounts are not associated with a university, and should have the field
    set to `null`.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized

    user_id = str(uuid4())
    user, database_user = create_user_from_new_user(user_id, new_user)
    validate_user(user)
    insert("users", user_id, database_user)
    return user

@app.get("/users/list", tags=["users"])
async def users_list(current_user: Annotated[User, Depends(get_current_user)]):
    """
    List all users. 
    
    Only `admin` accounts may list users.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    
    return [User(**user) for user in database.data["users"].values()]

class UserUpdate(BaseModel):
    id: str = Field(example="user-id")
    data: NewUser

# profile updating & password changing are the same operation, 
# for implementation simplicity (not the focus of the assignment)
@app.post("/users/update", tags=["users"])
async def users_update(current_user: Annotated[User, Depends(get_current_user)], update: UserUpdate):
    """
    Update an existing user. 
    
    Only `admin` accounts may list users.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    assert_user_by_id(update.id)
    
    user, database_user = create_user_from_new_user(update.id, update.user_data)
    validate_user(user)
    insert("users", update.id, database_user)
    return user

class UserDelete(BaseModel):
    id: str = Field(example="user-id")

@app.post("/users/delete", tags=["users"])
async def users_delete(current_user: Annotated[User, Depends(get_current_user)], delete: UserDelete):
    """
    Delete an existing user. 
    
    Only `admin` accounts may delete users.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if current_user.id == delete.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own user account")
    assert_user_by_id(delete.id)
    
    delete_user(delete.id)
    return { "success": True }

## universities

@app.post("/universities/create", tags=["universities"])
async def universities_create(current_user: Annotated[User, Depends(get_current_user)], new_university: UniversityData):
    """
    Create a new university. 
    
    Only `admin` accounts may create universities.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    
    id = str(uuid4())
    university = University(id=id, **new_university.model_dump())
    validate_university(university)
    insert("universities", id, university)
    return university

@app.get("/universities/list", tags=["universities"])
async def universities_list(current_user: Annotated[User, Depends(get_current_user)]):
    """
    List all universities. 
    
    Only `admin` accounts may list universities.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    
    return [University(**university) for university in database.data["universities"].values()]

class UniversityUpdate(BaseModel):
    id: str = Field(example="university-id")
    data: UniversityData

@app.post("/universities/update", tags=["universities"])
async def universities_update(current_user: Annotated[User, Depends(get_current_user)], update: UniversityUpdate):
    """
    Update an existing university. 
    
    Only `admin` accounts may update universities.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if update.id not in database.data["universities"]:
        raise HTTPException(status_code=400, detail=f"University with id '{update.id}' does not exist")
    
    university = University(id=update.id, **update.data.model_dump())
    validate_university(university)
    insert("universities", update.id, university)
    return university

class UniversityDelete(BaseModel):
    id: str = Field(example="university-id")

@app.post("/universities/delete", tags=["universities"])
async def universities_delete(current_user: Annotated[User, Depends(get_current_user)], delete: UniversityDelete):
    """
    Delete a university. 
    
    Only `admin` accounts may delete universities.

    This deletion will cascade, deleting all users, rooms, and times associated with the university.
    """
    if current_user.group != UserGroup.ADMIN:
        raise unauthorized
    if delete.id not in database.data["universities"]:
        raise HTTPException(status_code=400, detail=f"University with id '{delete.id}' does not exist")
    
    delete_university(delete.id)
    return { "success": True }

## rooms

class NewRoom(BaseModel):
    university: Optional[str] = Field(example="university-id", default=None)
    name: str

# this indirection is unfortunately necessary to allow `university`
# to be unspecified :(
# i'll leave it assymmetric with regards to how the other /create endpoints operate,
# as in theory i would like to eventually find a solution that removes this indirection,
# as opposed to introducing it to every other endpoint
class RoomCreate(BaseModel):
    room: NewRoom

@app.post("/rooms/create", tags=["rooms"])
async def rooms_create(current_user: Annotated[User, Depends(get_current_user)], create: RoomCreate):
    """
    Create a new room. 
    
    `manager` accounts may only create new rooms in the university they belong to. \\
    `admin` accounts may create new rooms in any university.
    """
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
    id: str = Field(example="room-id")
    name: str

@app.get("/rooms/list", tags=["rooms"])
async def rooms_list(current_user: Annotated[User, Depends(get_current_user)]):
    """
    List rooms. 
    
    `admin`s will see a list of every room in the system, along with it's accompanying university id. \\
    All other accounts will only see a list of rooms for the university they belong to, sans university id.
    """
    if current_user.group == UserGroup.ADMIN:
        return [Room(**room) for room in collection("rooms").values()]
    else:
        return [UniversityRoom(**room) for room in collection("rooms").values() if room["university"] == current_user.university]

class RoomUpdate(BaseModel):
    id: str = Field(example="room-id")
    data: NewRoom

@app.post("/rooms/update", tags=["rooms"])
async def rooms_update(current_user: Annotated[User, Depends(get_current_user)], update: RoomUpdate):
    """
    Update a room. 
    
    `admin`s may update any room in any university. \\
    `manager`s may only update rooms for the university they belong to.
    """
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
    id: str = Field(example="room-id")

@app.post("/rooms/delete", tags=["rooms"])
async def rooms_delete(current_user: Annotated[User, Depends(get_current_user)], delete: RoomDelete):
    """
    Delete a room. 
    
    `admin`s may delete any room in any university. \\
    `manager`s may only delete rooms for the university they belong to.

    This deletion will cascade, deleting all registered times for this room.
    """
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER]:
        raise unauthorized
    fetch_owned_room(current_user, delete.id)
    
    delete_room(delete.id)
    return { "success": True }

## times

class TimeDataWithOptionalRegistrant(RoomTimeData):
    registrant: Optional[str] = Field(example="user-id", default=None)

@app.post("/times/create", tags=["times"])
async def times_create(current_user: Annotated[User, Depends(get_current_user)], new_time: TimeDataWithOptionalRegistrant):
    """
    Register a new time. 
    
    `admin`s may create a time in any room, in any university, registered as belonging to any user. \\
    `manager`s may create a time in any room in the university they belong to, registered as belonging to any user. \\
    `personnel` may create a time in any room in the university they belong to, which is automatically registered as their own.

    Times registered in the same room must not overlap.
    """
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

@app.get("/times/list", tags=["times"])
async def times_list(current_user: Annotated[User, Depends(get_current_user)], room_id: str):    
    """
    List all times for a room. 
    
    `admin`s may list the times for any room in the system; all other users may only list times for rooms in the university they belong to.
    """
    fetch_owned_room(current_user, room_id)

    return [ListTime(**time) for time in collection("times").values() if time["room"] == room_id]

class TimeUpdate(BaseModel):
    id: str = Field(example="time-id")
    data: TimeDataWithOptionalRegistrant

@app.post("/times/update", tags=["times"])
async def times_update(current_user: Annotated[User, Depends(get_current_user)], update: TimeUpdate):   
    """
    Update a time. 
    
    `admin`s may update any time in any room, in any university, and they may register it as belonging to any user. \\
    `manager`s may update any time in any room in the university they belong to, any they may register it as belonging to any user. \\
    `personnel` may update only times they themselves have created. They may not change the ownership of those times.

    Times registered in the same room must not overlap.
    """
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
    id: str = Field(example="time-id")

@app.post("/times/delete", tags=["times"])
async def rooms_delete(current_user: Annotated[User, Depends(get_current_user)], delete: TimeDelete):
    """
    Delete a time. 
    
    `admin`s may delete any time in the system. \\
    `manager`s may delete any time registered to a room in the university they belong to. \\
    `personnel` may only delete times they themselves have registered.
    """
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER, UserGroup.PERSONNEL]:
        raise unauthorized
    time = fetch_owned_time(current_user, delete.id)
    if current_user.group not in [UserGroup.ADMIN, UserGroup.MANAGER] and time.registrant != current_user.id:
        raise HTTPException(status_code=400, detail=f"You may not delete registered times you did not create")
    
    delete_time(time.id)
    return { "success": True }