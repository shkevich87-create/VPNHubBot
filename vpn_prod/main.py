import asyncio
import os
from loguru import logger
from bot import bot_start
from aiohttp import web
from handlers.winkpay_callback import handle_winkpay_callback

os.makedirs('logs', exist_ok=True)
logger.add("logs/bot.log", rotation="1 day", compression="zip", 
           encoding="utf-8", format="{time} | {level} | {message}",
           level="INFO")

async def start_web_server():
    """Запуск веб-сервера для обработки callback от WinkPay"""
    app = web.Application()
    app.router.add_post("/winkpay/callback", handle_winkpay_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=9090)
    await site.start()
    logger.info("WinkPay callback сервер запущен на порту 9090")

async def main():
    """Главная функция для запуска бота и веб-сервера одновременно"""
    try:
        logger.info("Запуск бота и веб-сервера...")
        
        # Запускаем веб-сервер
        await start_web_server()
        
        # Запускаем бота (это блокирующая операция)
        await bot_start()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")

if __name__ == '__main__':
    asyncio.run(main())
