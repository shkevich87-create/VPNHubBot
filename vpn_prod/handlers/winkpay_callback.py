from aiogram import Router
from aiogram.types import Message
from aiohttp import web
from loguru import logger
import json
from handlers.winkpay import winkpay_manager

router = Router()

async def handle_winkpay_callback(request: web.Request):
    """
    Обработчик уведомлений от WinkPay об изменении статуса платежа.
    
    Согласно документации, уведомление (POST запрос) содержит данные 
    соответствующие GET /api/h2h/order/{order_id}
    
    Структура данных:
    {
        "order_id": "...",
        "external_id": "...",
        "status": "success/pending/fail",
        "sub_status": "successfully_paid/...",
        "amount": "...",
        "currency": "...",
        "payment_detail": {...},
        ...
    }
    """
    try:
        data = await request.json()
        order_id = data.get("order_id")
        status = data.get("status")
        sub_status = data.get("sub_status")
        external_id = data.get("external_id")

        logger.info(f"WinkPay callback получен: order_id={order_id}, status={status}, sub_status={sub_status}, external_id={external_id}")
        logger.debug(f"WinkPay callback полные данные: {json.dumps(data, ensure_ascii=False)}")

        # Проверяем успешность оплаты согласно документации
        # status: success, pending, fail
        # sub_status: successfully_paid, successfully_paid_by_resolved_dispute, accepted
        if status == "success" or sub_status in ["successfully_paid", "successfully_paid_by_resolved_dispute", "accepted"]:
            logger.info(f"WinkPay: платеж успешен для order_id={order_id}")
            # Можно вызвать ту же логику, что при check_payment
            # или обработать напрямую из данных callback
            await winkpay_manager.check_payment(order_id)
        elif status == "fail" or sub_status in ["canceled_by_dispute", "expired", "cancelled"]:
            logger.warning(f"WinkPay: платеж отменен/не выполнен для order_id={order_id}, sub_status={sub_status}")
        else:
            logger.debug(f"WinkPay: статус в обработке для order_id={order_id}, status={status}, sub_status={sub_status}")
            
        return web.Response(status=200, text="OK")
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в WinkPay callback: {e}")
        return web.Response(status=400, text="Bad Request")
    except Exception as e:
        logger.error(f"Ошибка при обработке callback WinkPay: {e}")
        return web.Response(status=500, text="Error")
