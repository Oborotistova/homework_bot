import logging
import os
import time
from http import HTTPStatus

import requests
from logging.handlers import RotatingFileHandler
from telegram import Bot

from dotenv import load_dotenv

load_dotenv()

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


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise 'отсутствие ответa API'
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    list_homeworks = response['homeworks']
    if len(list_homeworks) != 0:
        homework = list_homeworks[0]
    else:
        logger.error('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')
    return homework


def parse_status(homework):
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
    if homework_status == '':
        logger.debug('отсутствие в ответе новых статусов')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Доступность переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if response['homeworks'] is not []:
                message = parse_status(check_response(response))
                send_message(bot, message)
                logger.info('удачная отправка любого сообщения в Telegram')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error('сбой при отправке сообщения в Telegram')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
