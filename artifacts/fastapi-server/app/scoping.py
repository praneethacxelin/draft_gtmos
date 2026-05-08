"""Lookup helpers — no per-user ownership checks (auth removed)."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import Strategy, Account, Contact, Sequence, User


def own_strategy(db: Session, strategy_id: str, user: User) -> Strategy:
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    return s


def own_account(db: Session, account_id: str, user: User) -> Account:
    a = db.query(Account).filter(Account.id == account_id).first()
    if not a:
        raise HTTPException(404, "Account not found")
    return a


def own_contact(db: Session, contact_id: str, user: User) -> Contact:
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(404, "Contact not found")
    return c


def own_sequence(db: Session, sequence_id: str, user: User) -> Sequence:
    seq = db.query(Sequence).filter(Sequence.id == sequence_id).first()
    if not seq:
        raise HTTPException(404, "Sequence not found")
    return seq
