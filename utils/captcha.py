import random
import string
import io
from typing import Tuple
from captcha.image import ImageCaptcha

import os

class CaptchaGenerator:
    @staticmethod
    def generate_image_captcha() -> Tuple[io.BytesIO, str]:
        text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        font_path = os.path.join(os.path.dirname(__file__), 'arialblackcyrit_italic.ttf')
        image = ImageCaptcha(width=200, height=80, fonts=[font_path])
     
        
        data = image.generate(text)
        
        image_buffer = io.BytesIO()
        image_buffer.write(data.read())
        image_buffer.seek(0)
        
        return image_buffer, text
