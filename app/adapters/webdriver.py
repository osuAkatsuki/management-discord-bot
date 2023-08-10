from selenium import webdriver
from selenium.webdriver.remote.file_detector import LocalFileDetector

from app.common import settings


# Selenium is little weird so we need to make a class to handle all this weirdness
class WebDriver:
    def __init__(self):
        self.options = webdriver.ChromeOptions()
        self.options.add_argument("--headless")

    def capture_web_canvas(self, url: str, output_path: str):
        # create a new chrome session
        driver = webdriver.Remote(
            command_executor=settings.SELENIUM_DRIVER_URL,
            options=self.options,
        )
        driver.file_detector = LocalFileDetector()

        driver.get(url)

        # set the windows size to max canvas resolution
        S = lambda attribute: driver.execute_script(
            "return document.body.parentNode.scroll" + attribute,
        )
        driver.set_window_size(S("Width"), S("Height"))

        driver.find_element("tag name", "body").screenshot(output_path)
        driver.quit()
