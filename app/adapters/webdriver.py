import io
import tempfile
from typing import cast

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080


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
            driver.set_window_size(WINDOW_WIDTH, WINDOW_HEIGHT)

            # Get current viewport size
            (inner_width, inner_height) = driver.execute_script(
                "return [window.innerWidth, window.innerHeight]",
            )

            width_diff = WINDOW_WIDTH - inner_width
            height_diff = WINDOW_HEIGHT - inner_height

            # Set window so viewport becomes exactly 1920x1080
            driver.set_window_size(
                WINDOW_WIDTH + width_diff,
                WINDOW_HEIGHT + height_diff,
            )

            html_tag_el = driver.find_element("tag name", "html")
            return cast(bytes, html_tag_el.screenshot_as_png)

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
