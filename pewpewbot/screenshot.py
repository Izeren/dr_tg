import asyncio
import logging

from arsenic.session import Session
from pewpewbot.State import (
    SCREENSHOT_HEIGHT,
    SCREENSHOT_URL_KEY,
    SCREENSHOT_WIDTH,
    State,
)

from arsenic import browsers, services, start_session, stop_session, keys


class Screenshoter:
    def __init__(
        self, url=None, height=1000, width=1000, file_name="screenshot.png", loop=None
    ):
        self.url = url
        self.height = height
        self.width = width
        self.file_name = file_name
        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        service = services.Chromedriver()
        browser = browsers.Chrome(
            **{
                "goog:chromeOptions": {
                    "args": ["--headless", "--no-sandbox", "--disable-dev-shm-usage"],
                    "w3c": True
                }
            }
        )
        self.session: Session = loop.run_until_complete(start_session(service, browser))

    async def sync_with_state(self, state: State):
        # Update URL
        if (
            state.other.get(SCREENSHOT_URL_KEY)
            and state.other[SCREENSHOT_URL_KEY] != self.url
        ):
            self.url = state.other[SCREENSHOT_URL_KEY]
            await self.session.get(self.url)
            if "docs.google.com" in self.url:
                await self.hide_topbar_gdocs()
            logging.info(f"Updated url to {self.url}")

        # Update page size
        if (
            int(state.other[SCREENSHOT_WIDTH]) != self.width
            or int(state.other[SCREENSHOT_HEIGHT]) != self.height
        ):
            self.width = int(state.other[SCREENSHOT_WIDTH])
            self.height = int(state.other[SCREENSHOT_HEIGHT])
            await self.session.set_window_size(self.width, self.height)
            logging.info(f"Updated window size to {self.width}x{self.height}")

    async def hide_topbar_gdocs(self):
        elem = await self.session.get_element("body")
        await elem.send_keys(f"{keys.CONTROL}{keys.SHIFT}F")

    async def update_screenshot(self, state):
        logging.info(f"Updating screenshot...")
        await self.sync_with_state(state)
        if self.url is None:
            logging.info(f"URL not set.")
            return
        image_bytes = await self.session.get_screenshot()
        with open(self.file_name, "wb") as f:
            f.write(image_bytes.read())

    def __del__(self):
        try:
            logging.info("Shutting down browser session...")
            stop_session(self.session)
        except AttributeError:  # if session does not exist, do nothing
            pass
