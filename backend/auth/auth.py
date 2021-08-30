from ..database import db, User
from flask_user import SQLAlchemyAdapter
from flask_user import UserManager
from datetime import timezone, datetime, timedelta
from flask_jwt_extended import get_jwt, create_access_token, get_jwt_identity, set_access_cookies

user_manager = UserManager(SQLAlchemyAdapter(db, User))

def refresh_token(response):
  try:
    exp_timestamp = get_jwt()["exp"]
    print("exp timestamp", exp_timestamp)
    now = datetime.now(timezone.utc)
    target_timestamp = datetime.timestamp(now + timedelta(minutes=30))
    if target_timestamp > exp_timestamp:
        access_token = create_access_token(identity=get_jwt_identity()) 
        set_access_cookies(response, access_token)
    return response
  except (RuntimeError, KeyError):
      return response