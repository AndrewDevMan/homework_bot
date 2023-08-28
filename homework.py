import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import BadStatusCodeResponse, InvalidData

load_dotenv()
logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def logger_setup() -> None:
    """Настройка логгера."""
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        '%(name)s - %(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    logger.debug('Проверка наличия токенов')
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        logger.info(f'Отправка сообщения в Telegram - "{message}"')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.TelegramError as e:
        logger.error(f'Ошибка отправки сообщения - {e}', exc_info=True)
    else:
        logger.debug('Сообщение отправлено')


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к эндпоинту API-сервиса."""
    HEADERS['Accept'] = 'application/json'
    request_param = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    logger.info(
        'Запрос к API. {url}, {headers}, {params}'.format(**request_param)
    )
    try:
        homework_statuses = requests.get(**request_param)
    except requests.RequestException as e:
        logger.error(
            f'Ошибка при запросе к API: {e}'
            '{url}, {headers}, {params}'.format(**request_param),
            exc_info=True,
        )
    else:
        if homework_statuses.status_code != HTTPStatus.OK:
            msg_error = (
                f'Эндпоинт не доступен'
                f'Код ответа: {homework_statuses.status_code}'
            )
            logger.error(msg_error)
            raise BadStatusCodeResponse(msg_error)
        logger.debug('Ответ от API получен')
        return homework_statuses.json()


def check_response(response: dict) -> list:
    """Проверяет ответ от API на корректность."""
    logger.info('Проверка ответа API')
    if not isinstance(response, dict):
        msg_error = 'Ответ от API прислал не словарь'
        logger.error(msg_error)
        raise TypeError(msg_error)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        msg_error = 'Ответ от API прислал не список'
        logger.error(msg_error)
        raise TypeError(msg_error)
    return homeworks


def parse_status(homework: dict) -> str:
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as e:
        msg_error = f'В ответе нет запрашиваемого ключа - {e}'
        logger.error(msg_error, exc_info=True)
        raise KeyError(msg_error)
    if homework_status not in HOMEWORK_VERDICTS:
        msg_error = 'Недокументированный статус домашней работы'
        logger.error(msg_error)
        raise InvalidData(msg_error)
    else:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные токены,'
                        'работа бота будет завершина.')
        return None
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    previous_message = ''
    send_message(bot, '"Бот начал работу"')

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Статус не изменился'
            if message != previous_message:
                send_message(bot, message)
                logger.debug(message)
                previous_message = message
            else:
                logger.info(message)

        except (telegram.TelegramError, KeyError, TypeError, InvalidData,
                BadStatusCodeResponse, requests.RequestException) as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger_setup()
    main()
