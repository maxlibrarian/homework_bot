import logging
import os
import requests
import time
from telebot import TeleBot
from dotenv import load_dotenv

load_dotenv()


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


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


def check_tokens():
    """Проверка наличия необходимых переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        logging.critical(
            f'Отсутствуют обяательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        raise ValueError('Отсутствуют обязательные переменные окружения')


def send_message(bot, message):
    """Отправка сообщения в ТГ."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения в Telegram: {error}')
        try:
            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID, text=f'Сбой при отправке сообщения: '
                f'{error}'
            )
        except Exception as send_error_fall:
            logging.error(
                f'Не удалось отправить уведомление об ошибке: '
                f'{send_error_fall}'
            )


def get_api_answer(timestamp):
    """Получение ответа от API ЯП."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != 200:
            error_message = f'API вернул код {response.status_code}'
            logging.error(error_message)
            raise ConnectionError(error_message)
        return response.json()
    except requests.RequestException as error:
        error_message = f'Ошибка при запросе к API: {error}'
        logging.error(error_message)
        raise ConnectionError(error_message)


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        error_message = 'Ответ API не является словарем'
        logging.error(error_message)
        raise TypeError(error_message)

    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        error_message = '"homeworks" не содержит список'
        logging.error(error_message)
        raise TypeError(error_message)

    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        error_message = 'В ответе API домашки отсутствует ключ "homework_name"'
        logging.error(error_message)
        raise KeyError(error_message)

    status = homework.get('status')

    if status not in HOMEWORK_VERDICTS:
        error_message = f'Неизвестный статус работы: {status}'
        logging.error(error_message)
        raise ValueError(error_message)

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
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
                logging.debug('В ответе API отсутствуют новые статсы')

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
