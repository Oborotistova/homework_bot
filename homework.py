import logging
import os
import time
from http import HTTPStatus
from typing import List

import requests
from logging.handlers import RotatingFileHandler
from telegram import Bot

from dotenv import load_dotenv

load_dotenv()


def init_logger():
    """Конфигурация логгирования."""
    logging.basicConfig(
        filename='main.log',
        filemode='w',
        format='%(asctime)s, %(levelname)s, %(message)s',
        level=logging.DEBUG)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler('my_logger.log',
                                  maxBytes=50000000,
                                  backupCount=5)
    logger.addHandler(handler)
    formatter = logging.Formatter(
        '%(asctime)s, %(levelname)s, (%(filename)s).%(funcName)s(%(lineno)d),'
        '%(message)s'
    )
    handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(formatter))
    return logger


logger = init_logger()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message: str) -> str:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(current_timestamp: int) -> List:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise 'отсутствие ответa API'
    try:
        return response.json()
    except ValueError as error:
        logger.error(f'Формат ответa не json(): {error}')


def check_response(response: dict) -> str:
    """Проверяет ответ API на корректность."""
    try:
        list_homeworks = response['homeworks']
    except KeyError:
        logger.error('Отсутствует ключ "homeworks" в ответе API')
        raise KeyError('Отсутствует ключ "homeworks" в ответе API')
    if len(list_homeworks) != 0:
        return list_homeworks[0]
    logger.error('Список домашних работ пуст')
    raise IndexError('Список домашних работ пуст')


def parse_status(homework: dict) -> str:
    """Извлекает из информации о конкретной домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logger.error(
            f'недокументированный статус домашней работы {homework_status}')
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            message = parse_status(check_response(response))
            send_message(bot, message)
            logger.info('удачная отправка любого сообщения в Telegram')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error('сбой при отправке сообщения в Telegram')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
