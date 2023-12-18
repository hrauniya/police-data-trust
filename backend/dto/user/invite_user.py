from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class MemberRole(str, Enum):
    ADMIN = "Administrator"
    PUBLISHER = "Publisher"
    MEMBER = "Member"
    SUBSCRIBER = "Subscriber"


class InviteUserDTO(BaseModel):
    email: EmailStr
    role:  MemberRole

