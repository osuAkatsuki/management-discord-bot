import io
import tempfile
from selenium import webdriver
from selenium.webdriver.remote.file_detector import LocalFileDetector

from app.common import settings
from PIL import Image


# Selenium is little weird so we need to make a class to handle all this weirdness
class WebDriver:
    def __init__(self):
        self.options = webdriver.ChromeOptions()
        self.options.add_argument("--headless")

    def _capture_web_canvas(
        self,
        url: str,
        *,
        dependency_files: dict[str, bytes],
    ) -> bytes:
        with tempfile.TemporaryDirectory() as temp_dir:
            for filename, file_content in dependency_files.items():
                with open(f"{temp_dir}/{filename}", "wb") as f:
                    f.write(file_content)

            # create a new chrome session
            with webdriver.Remote(
                command_executor=settings.SELENIUM_DRIVER_URL,
                file_detector=LocalFileDetector(),
                options=self.options,
            ) as driver:
                driver.get(url)

                # set the windows size to max canvas resolution
                S = lambda attribute: driver.execute_script(
                    "return document.body.parentNode.scroll" + attribute,
                )
                driver.set_window_size(S("Width"), S("Height"))

                body_tag_el = driver.find_element("tag name", "body")
                return body_tag_el.screenshot_as_png

    def capture_html_as_jpeg_image(
        self,
        html_content: str,
        *,
        dependency_files: dict[str, bytes],
    ) -> bytes:
        with tempfile.TemporaryFile() as input_file:
            input_file.write(html_content.encode())
            input_file.seek(0)

            # Capture an image of the html content as a png file
            image_content = self._capture_web_canvas(
                f"file://{input_file.name}",
                dependency_files=dependency_files,
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
