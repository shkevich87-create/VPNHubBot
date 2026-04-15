import asyncio
import logging
import uuid


from yookassa import Configuration, Payment

from bot.keyboards.inline.user_inline import pay_and_check
from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization, get_lang

log = logging.getLogger(__name__)

_ = Localization.text


class KassaSmart(PaymentSystem):
    CHECK_ID: str = None
    ID: str = None
    EMAIL: str

    def __init__(self,
                 config,
                 message,
                 user_id,
                 price,
                 email=None):
        super().__init__(message, user_id, price)
        self.ACCOUNT_ID = int(config.yookassa_shop_id)
        self.SECRET_KEY = config.yookassa_secret_key
        self.EMAIL = email

    async def create(self):
        self.ID = str(uuid.uuid4())

    async def check_payment(self):
        Configuration.account_id = self.ACCOUNT_ID
        Configuration.secret_key = self.SECRET_KEY
        tic = 0
        while tic < self.CHECK_PERIOD:
            res = await Payment.find_one(self.ID)
            if res.status == 'succeeded':
                await self.successful_payment(
                    self.price,
                    'YooKassaSmart',
                )
                return
            tic += self.STEP
            await asyncio.sleep(self.STEP)
        return

    async def invoice(self, lang_user):
        bot = await self.message.bot.me()
        payment = await Payment.create({
            "amount": {
                "value": self.price,
                "currency": "RUB"
            },
            "receipt": {
                "customer": {
                    "full_name": self.message.from_user.full_name,
                    "email": self.EMAIL,
                },
                "items": [
                    {
                        "description": _('description_payment', lang_user),
                        "quantity": "1.00",
                        "amount": {
                            "value": self.price,
                            "currency": "RUB"
                        },
                        "vat_code": "2",
                        "payment_mode": "full_payment",
                        "payment_subject": "commodity"
                    },
                ]
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f'https://t.me/{bot.username}'
            },
            "capture": True,
            "description": _('description_payment', lang_user),
        }, self.ID)
        self.ID = payment.id
        return payment.confirmation.confirmation_url

    async def to_pay(self):
        await self.create()
        Configuration.account_id = self.ACCOUNT_ID
        Configuration.secret_key = self.SECRET_KEY
        lang_user = await get_lang(self.user_id)
        link_invoice = await self.invoice(lang_user)
        await self.message.answer(
            _('payment_balance_text', lang_user).format(price=self.price),
            reply_markup=await pay_and_check(link_invoice, lang_user)
        )
        log.info(
            f'Create payment link YooKassaSmart '
            f'User: (ID: {self.user_id}'
        )
        try:
            await self.check_payment()
        except Exception as e:
            log.error(e, 'The payment period has expired')

    def __str__(self):
        return 'YooKassaSmart payment system'
