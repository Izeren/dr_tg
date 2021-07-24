from ast import literal_eval
from dataclasses import asdict
import datetime
import logging
import os
import re
import decorator
import pathlib
import requests
from aiogram.types import InputFile
from marshmallow import EXCLUDE

from aiogram import types, Bot

import code_utils
import patterns
import views
from pewpewbot.models import Status, Koline, CodeVerdict, StatusSchema
from pewpewbot import utils
from pewpewbot.errors import AuthenticationError, ConnectionError, ValidationError
from pewpewbot.manager import Manager

logger = logging.getLogger("bot")
logger.propagate = False


@decorator.decorator
async def safe_dzzzr_interaction(fn, bot: Bot, manager: Manager, **kwargs):
    try:
        return await fn(bot, manager, **kwargs)
    except AuthenticationError as e:
        logger.error(e)
        if manager.state.debug_chat_id is not None:
            await bot.send_message(manager.state.debug_chat_id, "Ошибка аутентификации в движке дозора")
    except ConnectionError as e:
        logger.error(e)
        if manager.state.debug_chat_id is not None:
            await bot.send_message(manager.state.debug_chat_id, "Ошибка подключения к движку дозора")
    except ValidationError as e:
        logger.error(e)
        if manager.state.debug_chat_id is not None:
            await bot.send_message(manager.state.debug_chat_id, "Ошибка валидации ответа")
    except Exception as e:
        logger.error(e)
        if manager.state.debug_chat_id is not None:
            await bot.send_message(manager.state.debug_chat_id, "Неожиданное исключение в боте")


async def dummy(message: types.Message, manager: Manager, **kwargs):
    await message.reply("Вы пытаетесь использовать команду {}, но у нее еще нет реализации"
                        .format(kwargs['command_name']))


@safe_dzzzr_interaction
async def img(message: types.Message, manager: Manager, **kwargs):
    screenshot_path = manager.screenshoter.file_name
    smart_path = pathlib.Path(screenshot_path)
    if not smart_path.is_file():
        await message.reply("URL не настроен или ещё не сделано ни одного скриншота")
        return
    mtime = smart_path.stat().st_mtime
    age_in_seconds = int(datetime.datetime.today().timestamp() - mtime)
    await message.reply_photo(InputFile(screenshot_path),
                              "Штабной док\n последнее обновление было {} секунд назад".format(age_in_seconds))


async def parse_coords_to_location(message: types.Message, manager: Manager, **kwargs):
    await message.reply("Вы пытаетесь использовать команду {}, но у нее еще нет реализации"
                        .format(kwargs['command_name']))


async def update_ko(message: types.Message, manager: Manager, **kwargs):
    koline = await manager.get_or_load_and_parse_koline()


async def send_ko(message: types.Message, manager: Manager, **kwargs):
    koline = await manager.get_or_load_and_parse_koline()
    if not manager.state.tip:
        for sector in koline.sectors:
            await utils.notify_code_chat(manager, views.sector_default_ko_message(sector, manager.state))
    else:
        for sector, sector_tip in zip(koline.sectors, manager.state.tip):
            await utils.notify_code_chat(manager, views.not_taken_with_tips(sector, sector_tip, manager.state))


async def process_link(message: types.Message, manager: Manager, **kwargs):
    text = utils.trim_command_name(message, kwargs['command_name']).strip()
    if text:
        manager.state.link = text
        await message.reply("Установлена ссылка {}".format(text))
    else:
        link = manager.state.link
        if link:
            await message.reply("Ссылка: {}".format(link))
        else:
            await message.reply("Настройки ссылки не найдено")


async def process_tip(message: types.Message, manager: Manager, **kwargs):
    text = utils.trim_command_name(message, kwargs['command_name']).strip()
    if text.startswith('clean'):
        manager.state.reset('tip')
        await message.reply("Запиненная подсказка сброшена")
    elif text:
        manager.state.set_tip(text)
        await message.reply("Подсказка запинена на текущий уровень")
    else:
        tip_text = manager.state.tip
        if tip_text:
            await message.reply("Запиненная подсказка: {}".format(tip_text))
        else:
            await message.reply("Нет запиненной подсказки")


async def process_pattern(message: types.Message, manager: Manager, **kwargs):
    text = utils.trim_command_name(message, kwargs['command_name']).strip()
    # 'standar' is for stability to parse both standart and standard
    if 'standar' in text:
        manager.state.reset('code_pattern')
        await message.reply("Установлен стандартный шаблон кода")
    elif text:
        try:
            re.compile(text)
        except re.error:
            await message.reply("'{}' не является регулярным выражением. Шаблон кода не установлен".format(text))
        manager.state.code_pattern = text
        await message.reply("Шаблон кода установлен: {}".format(text))
    else:
        if manager.state.code_pattern:
            await message.reply("Шаблон кода: {}".format(manager.state.code_pattern))
        else:
            await message.reply("Шаблон кода: стандартный")


async def process_parse(message: types.Message, manager: Manager, **kwargs):
    await process_bool_setting(
        message=message,
        manager=manager,
        state_field='parse_on',
        desc="Парсинг",
        command_name=kwargs['command_name'])


async def process_maps(message: types.Message, manager: Manager, **kwargs):
    await process_bool_setting(
        message=message,
        manager=manager,
        state_field='maps_on',
        desc="Парсинг координат из чата",
        command_name=kwargs['command_name'])


async def process_type(message: types.Message, manager: Manager, **kwargs):
    await process_bool_setting(
        message=message,
        manager=manager,
        state_field='type_on',
        desc="Автоматический парсинг кодов",
        command_name=kwargs['command_name'])


async def process_bool_setting(message: types.Message, manager: Manager, state_field: str, desc: str,
                               command_name: str):
    """
    Updates bool settings from message in state.
    """
    text = utils.trim_command_name(message, command_name).strip()
    mode = utils.parse_new_mode(text)
    if mode is None:
        await message.reply("Неверный режим использования, используйте 'on' или 'off'")
    else:
        setattr(manager.state, state_field, mode)
        await message.reply(f"{desc} {utils.get_text_mode_status(mode)}")


async def get_bot_status(message: types.Message, manager: Manager, **kwargs):
    text = '''Режим работы бота:
--- Парсинг движка {}
--- Автоматический ввод кодов {}
--- Парсинг координат с локацией {}
'''
    formatted = text.format(
        utils.get_text_mode_status(manager.state.parse_on),
        utils.get_text_mode_status(manager.state.type_on),
        utils.get_text_mode_status(manager.state.maps_on)
    )
    await message.reply(formatted)


async def task(message: types.Message, manager: Manager, **kwargs):
    if manager.state and manager.state.game_status and manager.state.game_status.current_level:
        await message.reply(utils.format_level_message(manager.state.game_status.current_level.question),
                            parse_mode='Markdown')


@safe_dzzzr_interaction
async def login(message: types.Message, manager: Manager, **kwargs):
    text = utils.trim_command_name(message, kwargs['command_name']).strip()
    login, passwd = text.split(maxsplit=1)
    login = login.strip()
    passwd = passwd.strip()
    await manager.http_client.log_in(login, passwd)


@safe_dzzzr_interaction
async def process_code(message: types.Message, manager: Manager, **kwargs):
    if not manager.state.type_on:
        return
    text = message.text
    if text.startswith('.') or text.startswith('/'):
        text = text[1:]
    text = text.lower().strip()
    # TODO: make all awaits in the end
    await message.reply("Пытаюсь пробить код: {}".format(text))
    code_result = await manager.http_client.post_code(text)
    if isinstance(code_result.verdict, int):
        return await message.reply(code_result.comment)
    if code_result.verdict.value not in code_utils.GOOD_VERDICTS:
        return await message.reply(code_utils.CODE_VERDICT_TO_MESSAGE[code_result.verdict.value])
    else:
        if code_result.verdict.value == CodeVerdict.ACCEPTED_NEXT_LEVEL.value:
            await utils.notify_all_channels(manager, "Взят последний код на уровне")
            return await update_level_status(manager.bot, manager)
        await _update_current_level_info_on_code(
            code_utils.CODE_VERDICT_TO_MESSAGE[code_result.verdict.value], message, manager)
        if code_result.verdict.value in code_utils.ACCEPTED_VERDICTS:
            await send_ko(message, manager, **kwargs)


@safe_dzzzr_interaction
async def update_level(message: types.Message, manager: Manager, **kwargs):
    status_ref = utils.trim_command_name(message, kwargs['command_name'])
    if len(status_ref):
        if status_ref.startswith('{'):
            status_dict = status_ref
        elif '/' in status_ref:
            status_dict = requests.get(status_ref).text
        else:
            with open(f'test_game_states/{status_ref}') as f:
                status_dict = f.readline()
        try:
            game_status = StatusSchema(partial=True, unknown=EXCLUDE).load(literal_eval(status_dict))
        except Exception as e:
            game_status = StatusSchema(partial=True, unknown=EXCLUDE).load({})
            await message.reply('Не удалось распарсить игровой статус: {}'.format(e))
    else:
        game_status = await manager.http_client.status()
    # TODO: to be solved properly in issue #32
    await message.reply(str(game_status)[:4000])
    await update_level_status(manager.bot, manager, **{'game_status': game_status})


async def _process_next_level(status, manager: Manager, silent=True):
    manager.logger.info("New game status from site {} ".format(status))
    _update_current_level_info(status, manager)
    manager.state.reset('code_pattern')
    manager.state.reset('tip')
    if silent:
        return
    await utils.notify_all_channels(manager, "Выдан новый уровень")
    if not status:
        await utils.notify_all_channels(manager, "Не удалось загрузить статус по игре")
        return
    if not status.current_level:
        await utils.notify_all_channels(manager, "Не удалось загрузить статус по уровню")
        return
    if status.current_level.question:
        await utils.notify_all_channels(manager, utils.format_level_message(status.current_level.question))
        schema_urls = utils.get_schema_urls(status.current_level.question)
        if len(schema_urls):
            for schema_url in schema_urls:
                try:
                    await utils.image_to_all_channels(manager, "Схема захода: \n", schema_url)
                except Exception as e:
                    await utils.notify_debug_chat(manager, f"Не удалось отправить картинку по адресу {schema_url}")
                    await utils.notify_debug_chat(manager, e)
        else:
            await utils.notify_all_channels(manager, "Схема захода: Не удалось распарсить")
    if status.current_level.locationComment:
        await utils.notify_all_channels(
            manager,
            utils.format_level_message(status.current_level.locationComment))


def _update_current_level_info(game_status: Status, manager: Manager):
    manager.state.game_status = game_status
    if not game_status.current_level:
        logger.info("Level info is empty")
        return
    if not game_status.current_level.koline:
        logger.info("Level with empty koline")
        return
    try:
        manager.state.koline = Koline.from_string(game_status.current_level.koline)
    except Exception as e:
        logger.error("Bad koline to parse: {}".format(game_status.current_level.koline))


async def _update_current_level_info_on_code(verdict: str, message: types.Message, manager: Manager):
    new_status = await manager.http_client.status()
    koline = manager.state.koline
    new_koline = Koline.from_string(new_status.current_level.koline)

    if not koline:
        logger.error("Koline has not been initialized on level")
        manager.state.koline = new_koline
        manager.state.game_status = new_status
        return
    if len(koline.sectors) != len(new_koline.sectors):
        logger.error("Number of sectors has been changed, probably level has been upped")
        return
    for old_sector, new_sector in zip(koline.sectors, new_koline.sectors):
        if len(old_sector.codes) != len(new_sector.codes):
            logger.error("Number of codes for sector: {} is broken".format(new_sector.name))
            return
        for old_code, new_code in zip(old_sector.codes, new_sector.codes):
            if not old_code.taken and new_code.taken:
                await message.reply(
                    "{} таймер: {}, метка: {}, ко: {}".format(
                        verdict,
                        datetime.timedelta(seconds=new_status.current_level.tm),
                        new_code.label + 1,
                        new_code.ko
                    )
                )
    manager.state.koline = new_koline
    manager.state.game_status = new_status


@safe_dzzzr_interaction
async def update_level_status(bot: Bot, manager: Manager, **kwargs):
    forced_update = 'game_status' in kwargs
    game_status = None
    if forced_update:
        game_status = kwargs['game_status']
    elif manager.state.parse_on:
        game_status = await manager.http_client.status()
    if not game_status or not game_status.current_level:
        return
    current_level_id = game_status.current_level.levelNumber
    # To avoid dummy messages to the chats on the bot or game startup
    if not manager.state.game_status:
        return await _process_next_level(game_status, manager)
    if manager.state.game_status.current_level.levelNumber != current_level_id:
        return await _process_next_level(game_status, manager, silent=False)
    return _update_current_level_info(game_status, manager)


async def try_process_coords(message: types.Message, manager: Manager, text: str):
    coords = re.findall(patterns.STANDARD_COORDS_PATTERN, text)
    for idx in range(len(coords) // 2):
        s_lat = coords[2 * idx]
        s_long = coords[2 * idx + 1]
        try:
            f_lat = float(s_lat)
            f_long = float(s_long)
            await manager.bot.send_location(message.chat.id, f_lat, f_long,
                                            reply_to_message_id=message.message_id)
        except Exception as e:
            await message.reply("Не удалось распарсить координаты из: '{}', '{}'"
                                .format(s_lat, s_long))


async def process_unknown(message: types.Message, manager: Manager, **kwargs):
    text = message.text.lower()
    if re.fullmatch(manager.state.code_pattern, text) or text.startswith('.'):
        await process_code(message, manager)
    elif manager.state.maps_on:
        await try_process_coords(message, manager, text)


async def process_get_chat_id(message: types.Message, manager: Manager, **kwargs):
    await message.reply("chat id: {}".format(message.chat.id))


async def pin_chat(message: types.Message, manager: Manager, **kwargs):
    if 'main' in message.text:
        setattr(manager.state, 'main_chat_id', str(message.chat.id))
        await message.reply("Установлен чат для организационной информации")
    elif 'code' in message.text:
        setattr(manager.state, 'code_chat_id', str(message.chat.id))
        await message.reply("Установлен чат для ввода кодов и штабных трансляций")
    elif 'debug' in message.text:
        setattr(manager.state, 'debug_chat_id', str(message.chat.id))
        await message.reply("Установлен чат для дебажных отчетов")
    else:
        await message.reply("Используйте один из допустимых аргументов: main, code, debug")


async def set_state_key_value(message: types.Message, manager: Manager, **kwargs):
    text = utils.trim_command_name(message, kwargs['command_name']).strip()
    key, value = text.split()
    try:
        setattr(manager.state, key, value)
        await message.reply(f"Для переменной {key} установлено значение: {value}")
    except AttributeError:
        await message.reply(f"Переменной {key} не существует")
    except ValueError:
        await message.reply(f"{value} - недопустимое значение для переменной {key}")


async def get_all_params(message: types.Message, manager: Manager, **kwargs):
    values = asdict(manager.state)
    text = "\n".join(f"{key}: {value}" for key, value in values.items())
    # TODO: to be solved properly in issue #32
    await message.reply(f"Все заданные переменные:\n{text[:4000]}")


async def get_version(message: types.Message, manager: Manager, **kwargs):
    msg = os.environ.get("VERSION", "Не задана")
    await message.reply(f"Версия бота: {msg}")


async def reset_to_default(message: types.Message, manager: Manager, **kwargs):
    key = utils.trim_command_name(message, kwargs['command_name']).strip()
    if len(key):
        try:
            manager.state.reset(key)
            await message.reply(f"Для переменной {key} установлено значение: {getattr(manager.state, key)}")
        except AttributeError:
            await message.reply(f"Переменной {key} не существует")
    else:
        manager.state.reset_all()
        await message.reply("Выполнен сброс к заводским настройкам")
