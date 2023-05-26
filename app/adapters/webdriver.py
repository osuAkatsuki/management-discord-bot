from selenium import webdriver
from selenium.webdriver.remote.file_detector import LocalFileDetector
import settings


class WebDriver(webdriver.Remote):
    def __init__(self, *args, **kwargs):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        super().__init__(
            command_executor=settings.SELENIUM_DRIVER_URL,
            options=options,
            *args,
            **kwargs,
        )
        self.file_detector = LocalFileDetector()

    def capture_web_canvas(self, url: str, output_path: str):
        self.get(url)

        # set the windows size to max canvas resolution
        S = lambda attribute: self.execute_script(
            "return document.body.parentNode.scroll" + attribute,
        )
        self.set_window_size(S("Width"), S("Height"))

        self.find_element("tag name", "body").screenshot(output_path)
