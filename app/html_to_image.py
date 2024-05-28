import io
import html2image
import tempfile

from PIL import Image


def render_html_as_image(
    html_content: str,
    *,
    output_image_size: tuple[int, int],
) -> Image.Image:
    with tempfile.TemporaryDirectory() as output_directory:
        browser_adapter = html2image.Html2Image(
            size=output_image_size,
            output_path=output_directory,
        )

        with tempfile.TemporaryFile(dir=output_directory) as output_file:
            browser_adapter.screenshot(
                html_str=html_content,
                save_as=output_file.name,
            )

        output_file.seek(0)
        image_content = output_file.read()

    with io.BytesIO(image_content):
        image = Image.open(image_content)
        image.load()

    return image
