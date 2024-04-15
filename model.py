from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from database import fetch, find

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