import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from selenium.common import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from bsky.bluesky_credentials import BlueSkyCredentials

WINDOW_SIZE = "--window-size=600,1000"
latest_rate_limit_exceed: Optional[datetime] = None


async def setup_selenium() -> Optional[WebDriver]:
    global latest_rate_limit_exceed
    if latest_rate_limit_exceed is None:
        primary_credentials = BlueSkyCredentials(
            user_name=os.environ.get("OBSERVER_LOGIN"),
            password=os.environ.get("OBSERVER_PASSWORD")
        )
        driver = await __setup_selenium__(
            credentials=primary_credentials
        )
        if driver is not None:
            return driver
        if primary_credentials.user_name and primary_credentials.password:
            latest_rate_limit_exceed = datetime.utcnow()
            logging.warning(f"Rate limit exceeded for {primary_credentials.user_name}")
            return await setup_selenium()
        return None
    delta = (datetime.utcnow() - latest_rate_limit_exceed).days
    if delta < 1:
        return await __setup_selenium__(
            credentials=BlueSkyCredentials(
                user_name=os.environ.get("OBSERVER_LOGIN_ALTERNATIVE"),
                password=os.environ.get("OBSERVER_PASSWORD_ALTERNATIVE")
            )
        )
    latest_rate_limit_exceed = None
    return await setup_selenium()


async def __setup_selenium__(
    credentials: BlueSkyCredentials
) -> Optional[WebDriver]:
    if not credentials.user_name or not credentials.password:
        return None
    logging.info("Setting up Selenium")
    if os.environ.get("IS_DOCKERIZED") != "1":
        driver_opts = webdriver.ChromeOptions()
        driver_opts.add_argument(WINDOW_SIZE)
        driver_opts.add_argument("--headless")
        driver_opts.binary_location = os.environ.get("LOCAL_DEVELOPMENT_CHROME_BINARY")
        driver = webdriver.Chrome(options=driver_opts)
    else:
        # let's give chromium standalone some time to boot
        await asyncio.sleep(2)
        driver_opts = webdriver.ChromeOptions()
        driver_opts.add_argument("--headless")
        driver_opts.add_argument(WINDOW_SIZE)
        driver = webdriver.Remote(
            options=driver_opts,
            command_executor="http://chrome:4444"
        )

    driver.get("https://bsky.app")
    await asyncio.sleep(2)
    sign_in_button = driver.find_element(
        By.XPATH,
        "//nav[@role='navigation']/div/div[position()=2]/button[position()=2]"
    )
    sign_in_button.click()

    username_field = driver.find_element(
        By.XPATH,
        "//input[@data-testid='loginUsernameInput']"
    )
    password_field = driver.find_element(
        By.XPATH,
        "//input[@data-testid='loginPasswordInput']"
    )
    username_field.send_keys(credentials.user_name)
    password_field.send_keys(credentials.password)
    await asyncio.sleep(8)
    sign_in_button = driver.find_element(
        By.XPATH,
        "//button[@data-testid='loginNextButton']"
    )
    sign_in_button.click()
    await asyncio.sleep(5)
    try:
        driver.find_element(By.XPATH, "//*[contains(text(), 'Rate Limit Exceeded')]")
    except NoSuchElementException:
        return driver
    return None
