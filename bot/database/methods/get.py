from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, select, func

from bot.database.main import engine
from bot.database.models.main import (
    Persons,
    Servers,
    Payments,
    StaticPersons,
    PromoCode,
    WithdrawalRequests, Groups
)
from bot.misc.util import CONFIG


async def get_person(telegram_id):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Persons).filter(Persons.tgid == telegram_id)
        result = await db.execute(statement)
        person = result.scalar_one_or_none()
        return person


async def get_person_id(list_input):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Persons).filter(Persons.tgid.in_(list_input))
        result = await db.execute(statement)
        persons = result.scalars().all()
        return persons


async def _get_person(db, tgid):
    statement = select(Persons).filter(Persons.tgid == tgid)
    result = await db.execute(statement)
    person = result.scalar_one_or_none()
    return person


async def _get_server(db, name):
    statement = select(Servers).filter(Servers.name == name)
    result = await db.execute(statement)
    server = result.scalar_one_or_none()
    return server


async def get_all_user():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Persons)
        result = await db.execute(statement)
        persons = result.scalars().all()
        return persons


async def get_all_subscription():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Persons).filter(Persons.banned == False)
        result = await db.execute(statement)
        persons = result.scalars().all()
        return persons


async def get_no_subscription():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Persons).filter(Persons.banned == True)
        result = await db.execute(statement)
        persons = result.scalars().all()
        return persons


async def get_payments():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Payments).options(
            joinedload(Payments.payment_id)
        )
        result = await db.execute(statement)
        payments = result.scalars().all()

        for payment in payments:
            payment.user = payment.payment_id.username

        return payments


async def get_all_server():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Servers)
        result = await db.execute(statement)
        servers = result.scalars().all()
        return servers


async def get_server(name):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        return await _get_server(db, name)


async def get_server_id(id_server):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Servers).filter(Servers.id == id_server)
        result = await db.execute(statement)
        server = result.scalar_one_or_none()
        return server


async def get_free_servers(group_name, type_vpn):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Servers).filter(
            and_(
                Servers.space < int(CONFIG.max_people_server),
                Servers.work,
                Servers.group == group_name,
                Servers.type_vpn == type_vpn
            )
        )
        result = await db.execute(statement)
        servers = result.scalars().all()
        if not servers:
            raise FileNotFoundError('Server not found')
        return servers


async def get_all_static_user():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(StaticPersons).options(
            joinedload(StaticPersons.server_table)
        )
        result = await db.execute(statement)
        all_static_user = result.scalars().all()
        return all_static_user


async def get_all_promo_code():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(PromoCode)
        result = await db.execute(statement)
        promo_code = result.scalars().all()
        return promo_code


async def get_promo_code(text_promo):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(PromoCode).options(
            joinedload(PromoCode.person)
        ).filter(
            PromoCode.text == text_promo
        )
        result = await db.execute(statement)
        promo_code = result.unique().scalar_one_or_none()
        return promo_code


async def get_count_referral_user(tgid):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(func.count(Persons.id)).filter(
            Persons.referral_user_tgid == tgid
        )
        result = await db.execute(statement)
        return result.scalar()


async def get_referral_balance(tgid):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Persons).filter(Persons.tgid == tgid)
        result = await db.execute(statement)
        person = result.scalar_one_or_none()
        return person.referral_balance


async def get_all_application_referral():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(WithdrawalRequests)
        result = await db.execute(statement)
        return result.scalars().all()


async def get_application_referral_check_false():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(WithdrawalRequests).filter(
            WithdrawalRequests.check_payment == False
        )
        result = await db.execute(statement)
        return result.scalars().all()


async def get_person_lang(telegram_id):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Persons).filter(Persons.tgid == telegram_id)
        result = await db.execute(statement)
        person = result.scalar_one_or_none()
        if person is None:
            return CONFIG.languages
        return person.lang


async def get_all_groups():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(
            Groups, func.count(Groups.users), func.count(Groups.servers)). \
            outerjoin(Groups.users). \
            outerjoin(Groups.servers). \
            group_by(Groups.id). \
            order_by(Groups.id)
        result = await db.execute(statement)
        rows = result.all()
        groups_with_counts = []
        for row in rows:
            group = row[0]
            count_user = row[1]
            count_server = row[2]
            groups_with_counts.append(
                {"group": group, "count_user": count_user,
                 "count_server": count_server})
        return groups_with_counts


async def get_group(group_id):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Groups).filter(Groups.id == group_id)
        result = await db.execute(statement)
        return result.scalar_one_or_none()


async def get_group_name(group_name):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Groups).filter(Groups.name == group_name)
        result = await db.execute(statement)
        return result.scalar_one_or_none()


async def get_users_group(group_id):
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(Groups).filter(Groups.id == group_id)
        result = await db.execute(statement)
        group = result.scalar_one_or_none()
        statement = select(Persons).filter(Persons.group == group.name)
        result = await db.execute(statement)
        return result.scalars().all()


async def get_count_groups():
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        statement = select(func.count(Groups.id))
        result = await db.execute(statement)
        count = result.scalar_one()
        return count
