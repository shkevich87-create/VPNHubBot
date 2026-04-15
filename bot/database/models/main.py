from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey, Table, \
    UniqueConstraint, BigInteger
from sqlalchemy import Float, DateTime, Boolean

from bot.database.main import engine
from bot.misc.util import CONFIG


class Base(DeclarativeBase):
    pass


class Groups(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True)
    servers = relationship('Servers', back_populates="group_tabel")
    users = relationship('Persons', back_populates="group_tabel")


class Persons(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    tgid = Column(BigInteger, unique=True)
    banned = Column(Boolean, default=False)
    notion_oneday = Column(Boolean, default=False)
    subscription = Column(BigInteger)
    balance = Column(Integer, default=0)
    username = Column(String)
    fullname = Column(String)
    referral_user_tgid = Column(BigInteger, nullable=True)
    referral_balance = Column(Integer, default=0)
    lang = Column(String, default=CONFIG.languages)
    lang_tg = Column(String, nullable=True)
    server = Column(
        Integer,
        ForeignKey("servers.id", ondelete='SET NULL'),
        nullable=True)
    server_table = relationship("Servers", back_populates="users")
    group = Column(
        String,
        ForeignKey("groups.name", ondelete='SET NULL'),
        nullable=True)
    group_tabel = relationship(Groups, back_populates="users")
    payment = relationship('Payments', back_populates='payment_id')
    promocode = relationship(
        'PromoCode',
        secondary='person_promocode_association',
        back_populates='person'
    )
    withdrawal_requests = relationship(
        'WithdrawalRequests',
        back_populates='person'
    )


class Servers(Base):
    __tablename__ = 'servers'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    type_vpn = Column(Integer, nullable=False)
    outline_link = Column(String, unique=True)
    ip = Column(String, nullable=False)
    connection_method = Column(Boolean)
    panel = Column(String)
    inbound_id = Column(Integer)
    password = Column(String)
    vds_password = Column(String)
    login = Column(String)
    work = Column(Boolean, default=True)
    space = Column(Integer, default=0)
    group = Column(
        String,
        ForeignKey("groups.name", ondelete='SET NULL'),
        nullable=True)
    group_tabel = relationship(Groups, back_populates="servers")
    users = relationship(Persons, back_populates="server_table")
    static = relationship("StaticPersons", back_populates="server_table")

    @classmethod
    def create_server(cls, data):
        return cls(**data)


class Payments(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True, index=True)
    user = Column(Integer, ForeignKey("users.id"))
    payment_id = relationship(Persons, back_populates="payment")
    payment_system = Column(String)
    amount = Column(Float)
    data = Column(DateTime)


class StaticPersons(Base):
    __tablename__ = 'static_persons'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    server = Column(Integer, ForeignKey("servers.id", ondelete='SET NULL'))
    server_table = relationship("Servers", back_populates="static")


class PromoCode(Base):
    __tablename__ = 'promocode'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, unique=True, nullable=False)
    add_balance = Column(Integer, nullable=False)
    person = relationship(
        'Persons',
        secondary='person_promocode_association',
        back_populates='promocode',
    )


message_button_association = Table(
    'person_promocode_association',
    Base.metadata,
    Column('promocode_id', Integer, ForeignKey(
        'promocode.id', ondelete='CASCADE'
    )),
    Column('users_id', Integer, ForeignKey(
        'users.id', ondelete='CASCADE'
    )),
    UniqueConstraint('promocode_id', 'users_id', name='uq_users_promocode')
)


class WithdrawalRequests(Base):
    __tablename__ = 'withdrawal_requests'
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)
    payment_info = Column(String, nullable=False)
    communication = Column(String)
    check_payment = Column(Boolean, default=False)
    user_tgid = Column(BigInteger, ForeignKey("users.tgid"))
    person = relationship("Persons", back_populates="withdrawal_requests")


async def create_all_table():
    async_engine = engine()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
