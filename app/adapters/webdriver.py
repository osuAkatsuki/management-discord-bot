import io
import tempfile
from typing import cast

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class WebDriver:
    def __init__(self) -> None:
        self.options = Options()
        self.options.add_argument("--headless")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")

    def _capture_web_canvas(
        self,
        url: str,
    ) -> bytes:
        # create a new chrome session
        with webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=self.options,
        ) as driver:
            driver.get(url)
            driver.set_window_size(1920, 1080)

            body_tag_el = driver.find_element("tag name", "body")
            return cast(bytes, body_tag_el.screenshot_as_png)

    def capture_html_as_jpeg_image(
        self,
        html_content: str,
    ) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".html") as input_file:
            input_file.write(html_content.encode())
            input_file.seek(0)

            # Capture an image of the html content as a png file
            image_content = self._capture_web_canvas(
                f"file://{input_file.name}",
            )

        with (
            io.BytesIO(image_content) as input_buffer,
            io.BytesIO() as output_buffer,
        ):
            image = Image.open(input_buffer)
            image = image.convert("RGB")  # RGBA -> RGB
            image.load()

            image.save(
                output_buffer,
                format="JPEG",
                subsampling=0,
                quality=100,
            )

            return output_buffer.getvalue()
