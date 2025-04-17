import logging
import requests
import time
from constants import (
    PRACTICUM_TOKEN,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
    HEADERS,
    HOMEWORK_VERDICTS,
    ENDPOINT,
    RETRY_PERIOD
)
from http import HTTPStatus
from telebot import TeleBot


MISSING_TOKENS_ERROR = 'Отсутствуют обязательные переменные окружения: {}'
INVALID_STATUS_ERROR = 'Неизвестный статус работы: {}'
MISSING_KEY_ERROR = 'В ответе API домашки отсутствует ключ "{}"'
API_REQUEST_ERROR = 'Ошибка при запросе к API: {}'
UNEXPECTED_RESPONSE_FORMAT = 'Неожиданный формат ответа API: {}'
SERVER_ERROR_MESSAGE = 'Сервер вернул ошибку: {}'
NO_NEW_STATUSES = 'В ответе API отсутствуют новые статусы'
STATUS_UPDATE_TEMPLATE = 'Изменился статус проверки работы "{}". {}'
API_ERROR_TEMPLATE = (
    'Ошибка при запросе к API. URL: {0}, Headers: {1}, Params: {2}'
)
CONNECTION_ERROR = 'Ошибка при отправке сообщения в Telegram: {}'
GENERAL_FAILURE = 'Сбой в работе программы: {}'
API_RESPONSE_NOT_DICT = 'Ответ API не является словарем'
API_RESPONSE_NOT_LIST = '{} не содержит список'


def check_tokens():
    """Проверка наличия необходимых переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        logging.critical(MISSING_TOKENS_ERROR.format(missing_tokens))
        raise ValueError(MISSING_TOKENS_ERROR.format(missing_tokens))


def send_message(bot, message):
    """Отправка сообщения в ТГ."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение успешно отправлено: {message}')
    except ConnectionError as error:
        raise ConnectionError(CONNECTION_ERROR.format(error))


def get_api_answer(timestamp):
    """Получение ответа от API ЯП."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError(
                API_ERROR_TEMPLATE.format(ENDPOINT, HEADERS, payload)
            )
        return response.json()
    except requests.RequestException:
        raise ConnectionError(
            API_ERROR_TEMPLATE.format(ENDPOINT, HEADERS, payload)
        )


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError(API_RESPONSE_NOT_DICT)

    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(API_RESPONSE_NOT_LIST.format('homeworks'))
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        error_message = MISSING_KEY_ERROR.format('homework_name')
        raise KeyError(error_message)

    status = homework.get('status')

    if not status:
        raise KeyError(MISSING_KEY_ERROR.format('status'))

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(INVALID_STATUS_ERROR.format(status))

    verdict = HOMEWORK_VERDICTS[status]
    return STATUS_UPDATE_TEMPLATE.format(homework_name, verdict)


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    check_tokens()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                if message != previous_message:
                    send_message(bot, message)
                    previous_message = message
            else:
                logging.debug(NO_NEW_STATUSES)

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = GENERAL_FAILURE.format(error)
            logging.error(message)
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
