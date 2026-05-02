from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from handlers.database import db
import os
from datetime import datetime
from loguru import logger

router = Router()

@router.callback_query(F.data == "admin_get_all_payments_code")
async def get_all_payment_codes(callback: CallbackQuery):
    """Обработчик выгрузки всех кодов оплаты"""
    try:
        payment_codes = await db.get_all_payment_codes()
        
        if not payment_codes:
            await callback.answer("Коды оплаты отсутствуют", show_alert=True)
            return
        
        os.makedirs('temp', exist_ok=True)
        
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'temp/payment_codes_{current_time}.txt'
        
        with open(filename, 'w', encoding='utf-8') as file:
            for code in payment_codes:
                file.write('-' * 50 + '\n')
                file.write(f"Код: {code['pay_code']}\n")
                file.write(f"Сумма: {code['sum']} ₽\n")
                file.write(f"Статус: {'✅ Активен' if code['is_enable'] else '❌ Неактивен'}\n")
                file.write(f"Дата создания: {code['create_date']}\n")
            file.write('-' * 50 + '\n')
        
        document = FSInputFile(filename)
        await callback.message.answer_document(
            document,
            caption="📄 Выгрузка всех кодов оплаты"
        )
        
        os.remove(filename)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выгрузке кодов оплаты: {e}")
        await callback.answer(
            "Произошла ошибка при формировании файла",
            show_alert=True
        ) 