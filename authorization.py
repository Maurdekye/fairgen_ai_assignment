from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from model import UserPassword, get_user_by_id, get_user_by_name

secret_key = "CHANGEME_7ca47b62f5463f69baddaeed7e528cd1b58cc121783c718a5096186a06e7b08c"
token_expire = 30
jwt_algorithm = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# note: bcrypt warning appears in console due to outdated bcrypt support in the
# passlib package
# `(trapped) error reading bcrypt version`
# `AttributeError: module 'bcrypt' has no attribute '__about__'`
# see https://github.com/pyca/bcrypt/issues/684 for relevant information
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str):
    return pwd_context.hash(password)

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
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

def get_access_token(form_data: OAuth2PasswordRequestForm):
    user_dict = get_user_by_name(form_data.username)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    user = UserPassword(**user_dict)
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    expire = datetime.now(timezone.utc) + timedelta(minutes=token_expire)
    access_token = jwt.encode({"exp": expire, "sub": user.id }, secret_key, algorithm=jwt_algorithm)
    return { "access_token": access_token, "token_type": "bearer" }