from dataclasses import dataclass
from logging import Logger

from aiogram import Bot

from models import Koline
from pewpewbot.State import State
from pewpewbot.client import Client
from pewpewbot.screenshot import Screenshoter


@dataclass
class Manager:
    state: State
    http_client: Client
    screenshoter: Screenshoter
    bot: Bot
    logger: Logger

    async def get_or_load_and_parse_koline(self):
        if not self.state.koline:
            status = await self.http_client.status()
            self.state.koline = Koline.from_string(status.current_level.koline)
        return self.state.koline

    async def load_and_parse_koline(self):
        status = await self.http_client.status()
        self.state.game_status = status
        self.state.koline = Koline.from_string(status.current_level.koline)
        return self.state.koline
