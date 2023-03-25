import asyncio
import json
import redis

import aiohttp
import logging
from aiohttp import client_exceptions
from time import sleep
from environs import Env
from keyboard import get_start_keyboard, get_main_keyboard
from pprint import pprint
from textwrap import dedent


async def send_message(connect, chat_id, msg, *, reply_markup=None):
    """Отправка сообщения через api TG"""
    url = f"https://api.telegram.org/bot{connect['token']}/sendmessage"
    params = {
        'chat_id': chat_id,
        'text': msg,
        'reply_markup': reply_markup
    }
    for param, value in params.items():
        if value is None:
            del params[param]
    async with connect['session'].get(url, params=params) as res:
        res.raise_for_status()
        return json.loads(await res.text())


async def start(connect, event):
    event_info = await get_event_info(event)
    start_buttons = ['/start', '+']
    msg = 'MENU:'
    if event_info['user_reply'] in start_buttons:
        msg = f'''
            Привет, {event_info['first_name']}, я бот этого чата.
            Здесь ты можешь узнать всю актуальную информацию о наших курсах и при желании оставить заявку.
            Чтобы начать нажми "MENU"             
            '''
        await send_message(connect, event_info['chat_id'], dedent(msg), reply_markup=await get_start_keyboard())
        return 'START'
    await send_message(connect, event_info['chat_id'], msg, reply_markup=await get_main_keyboard(2))
    return 'START'


async def get_event_info(event):
    if event.get('message'):
        user_reply = event['message']['text']
        chat_id = event['message']['chat']['id']
        first_name = event['message']['chat']['first_name']
    elif event.get('callback_query'):
        user_reply = event['callback_query']['data']
        chat_id = event['callback_query']['message']['chat']['id']
        first_name = event['callback_query']['message']['chat']['first_name']
    else:
        return
    return {
        'user_reply': user_reply,
        'chat_id': chat_id,
        'first_name': first_name
    }


async def handle_event(connect, event):
    """Главный обработчик событий"""
    event_info = await get_event_info(event)
    if event_info['user_reply'].lower() in ['start', '/start', 'начать', 'старт', '+']:
        user_state = 'START'
    else:
        user_state = connect['redis_db'].get(f'tg_{event_info["chat_id"]}_bot').decode('utf-8')

    states_functions = {
        'START': start,
        ###################
        # Other functions #
        ###################
    }
    state_handler = states_functions[user_state]
    bot_state = await state_handler(connect, event)
    connect['redis_db'].set(f'tg_{event_info["chat_id"]}_bot', bot_state)


async def listen_server():
    """Получение событий сервера"""
    env = Env()
    env.read_env()
    logger = logging.getLogger('telegram')
    logger.setLevel(logging.WARNING)
    logger.warning('Tg-Бот "eyelash-courses" запущен')

    tg_token = env.str('TOKEN')
    redis_db = redis.Redis(
        host=env.str('REDIS_HOST'),
        port=env.int('REDIS_PORT'),
        password=env.str('REDIS_PASSWORD')
    )
    url = f'https://api.telegram.org/bot{tg_token}/getUpdates'
    params = {'timeout': 5, 'limit': 1}
    async with aiohttp.ClientSession() as session:
        connect = {'session': session, 'token': tg_token, 'redis_db': redis_db}
        while True:
            try:
                await asyncio.sleep(0.1)
                async with session.get(url, params=params) as res:
                    res.raise_for_status()
                    updates = json.loads(await res.text())
                if not updates.get('result') or not updates['ok']:
                    continue
                event = updates['result'][-1]
                pprint(event)
                params['offset'] = event['update_id'] + 1
                await handle_event(connect, event)
            except ConnectionError:
                sleep(5)
                logger.warning(f'Соединение было прервано', stack_info=True)
                continue
            except client_exceptions.ServerTimeoutError:
                logger.warning(f'Ошибка ReadTimeout', stack_info=True)
                continue
            except Exception as err:
                logger.exception(err)
                print(err)

if __name__ == '__main__':
    asyncio.run(listen_server())
