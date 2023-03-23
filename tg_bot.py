import asyncio
import json
from pprint import pprint
import aiohttp
import logging
from aiohttp import client_exceptions
from time import sleep
from environs import Env


async def send_message(session, token, chat_id, msg: str):
    """Отправка сообщения через api TG"""
    url = f"https://api.telegram.org/bot{token}/sendmessage"
    params = {'chat_id': chat_id, 'text': msg}
    async with session.get(url, params=params) as res:
        res.raise_for_status()
        return json.loads(await res.text())


async def listen_server():
    """Получение событий сервера"""
    env = Env()
    env.read_env()

    logger = logging.getLogger('telegram')
    logger.setLevel(logging.WARNING)
    logger.warning('Tg-Бот "eyelash-courses" запущен')

    tg_token = env.str('TOKEN')
    url = f'https://api.telegram.org/bot{tg_token}/getUpdates'
    params = {'timeout': 5, 'limit': 1}
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await asyncio.sleep(0.1)
                async with session.get(url, params=params) as res:
                    res.raise_for_status()
                    updates = json.loads(await res.text())
                    pprint(updates)
                    if not updates.get('result') or not updates['ok']:
                        continue
                    event = updates['result'][-1]
                    params['offset'] = event['update_id'] + 1
                    text = event['message']['text']
                    chat_id = event['message']['chat']['id']
                    await send_message(session, tg_token, chat_id, text)
            except ConnectionError as err:
                sleep(5)
                logger.warning(f'Соединение было прервано: {err}', stack_info=True)
                continue
            except client_exceptions.ServerTimeoutError as err:
                logger.warning(f'Ошибка ReadTimeout: {err}', stack_info=True)
                continue
            except Exception as err:
                logger.exception(err)
                print(err)

if __name__ == '__main__':
    asyncio.run(listen_server())
