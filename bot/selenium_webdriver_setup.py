import os
from time import sleep
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

WINDOW_SIZE = "--window-size=600,1000"


def setup_selenium() -> Optional[WebDriver]:
    if 'OBSERVER_LOGIN' not in os.environ.keys() or 'OBSERVER_PASSWORD' not in os.environ.keys():
        return None
    if os.environ.get("IS_DOCKERIZED") != "1":
        driver_opts = webdriver.ChromeOptions()
        driver_opts.add_argument("--headless")
        driver_opts.add_argument(WINDOW_SIZE)
        driver_opts.binary_location = os.environ.get("LOCAL_DEVELOPMENT_CHROME_BINARY")
        driver = webdriver.Chrome(options=driver_opts)
    else:
        # let's give chromium standalone some time to boot
        sleep(2)
        driver_opts = webdriver.ChromeOptions()
        driver_opts.add_argument("--headless")
        driver_opts.add_argument(WINDOW_SIZE)
        driver = webdriver.Remote(
            options=driver_opts,
            command_executor="http://chrome:4444"
        )

    driver.get("https://www.bsky.app")

    sign_in_button = driver.find_element(
        By.XPATH,
        "//button[@data-testid='signInButton']"
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
    username_field.send_keys(os.environ.get('OBSERVER_LOGIN'))
    password_field.send_keys(os.environ.get('OBSERVER_PASSWORD'))
    sleep(2)
    sign_in_button = driver.find_element(
        By.XPATH,
        "//button[@data-testid='loginNextButton']"
    )
    sign_in_button.click()
    sleep(5)
    return driver
