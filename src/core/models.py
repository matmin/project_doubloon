from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class User(BaseModel):
    id: Optional[int]
    name: str
    email: EmailStr
    created_at: Optional[datetime]


class Category(BaseModel):
    id: Optional[int]
    name: str
    parent_category_id: Optional[int]
    category_type: str
    is_shared: bool = False
    created_at: Optional[datetime]


class Transaction(BaseModel):
    id: Optional[int]
    user_id: int
    transaction_date: date
    amount: float
    description: str
    category_id: Optional[int]
    is_shared: bool = False
    shared_split_percentage: float = 50.0
    created_at: Optional[datetime]
