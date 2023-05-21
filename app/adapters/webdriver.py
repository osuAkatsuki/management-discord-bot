from selenium import webdriver


class WebDriver(webdriver.Chrome):
    def __init__(self, *args, **kwargs):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        super().__init__(options=options, *args, **kwargs)

    def capture_web_canvas(self, url: str, output_path: str):
        self.get(url)

        # set the windows size to max canvas resolution
        S = lambda attribute: self.execute_script(
            "return document.body.parentNode.scroll" + attribute,
        )
        self.set_window_size(S("Width"), S("Height"))

        self.find_element("tag name", "body").screenshot(output_path)
