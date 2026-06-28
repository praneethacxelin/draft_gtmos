"""Per-user ownership checks for data scoping.

Every resource lookup verifies that the resource belongs to the requesting
user (via ``user_id``). Admin users bypass the check and can access all
resources.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import Strategy, Account, Contact, Sequence, User


def _is_admin(user: User) -> bool:
    return bool(getattr(user, "is_admin", False))


def own_strategy(db: Session, strategy_id: str, user: User) -> Strategy:
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    if not _is_admin(user) and s.user_id is not None and s.user_id != user.id:
        raise HTTPException(404, "Strategy not found")
    return s


def own_account(db: Session, account_id: str, user: User) -> Account:
    a = db.query(Account).filter(Account.id == account_id).first()
    if not a:
        raise HTTPException(404, "Account not found")
    if not _is_admin(user) and a.user_id is not None and a.user_id != user.id:
        raise HTTPException(404, "Account not found")
    return a


def own_contact(db: Session, contact_id: str, user: User) -> Contact:
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(404, "Contact not found")
    if not _is_admin(user) and c.user_id is not None and c.user_id != user.id:
        raise HTTPException(404, "Contact not found")
    return c


def own_sequence(db: Session, sequence_id: str, user: User) -> Sequence:
    seq = db.query(Sequence).filter(Sequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(404, "Sequence not found")
    # Sequences don't have a direct user_id, so check via the linked contact.
    if not _is_admin(user):
        contact = db.query(Contact).filter(Contact.id == seq.contact_id).first()
        if contact and contact.user_id is not None and contact.user_id != user.id:
            raise HTTPException(404, "Sequence not found")
    return seq
