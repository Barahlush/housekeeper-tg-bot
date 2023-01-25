from random import choice

import requests
from config import GIPHY_API_KEY
from loguru import logger
from requests.exceptions import ReadTimeout
from urllib3.exceptions import ReadTimeoutError

SUCCESS_CODE = 200
GIPHY_URL = f'https://api.giphy.com/v1/gifs/trending?api_key={GIPHY_API_KEY}&limit=25&rating=g'   # noqa: E501
GPT_URL = 'https://pelevin.gpt.dobro.ai/generate/'
logger.info(GIPHY_URL)


def get_gpt_response(prompt: str) -> str:
    # Gets a response from GPT-3 at https://pelevin.gpt.dobro.ai/generate/

    request_body = {'prompt': prompt, 'length': 39}
    try:
        response = requests.post(
            GPT_URL,
            json=request_body,
            timeout=5,
        )
    except (ReadTimeout, ReadTimeoutError, TimeoutError) as e:
        logger.error('GPT-3 request timeout: {}', e)
        return ''
    except Exception:
        logger.exception('GPT-3 request failed')
        return ''

    if response.status_code != SUCCESS_CODE:
        logger.error('GPT-3 request failed: {}', response.text)
        return ''
    return str(response.json()['replies'][0])


def get_gif_url() -> str | None:
    # Gets a random GIF from Giphy at https://developers.giphy.com/docs/api/endpoint#trending

    try:
        response = requests.get(GIPHY_URL, timeout=5)
    except (ReadTimeout, ReadTimeoutError, TimeoutError) as e:
        logger.error('Giphy request timeout: {}', e)
        return None
    except Exception:
        logger.exception('Giphy request failed')
        return None

    if response.status_code != SUCCESS_CODE:
        logger.error('Giphy request failed: {}', response.text)
        return None
    gifs = response.json()['data']
    return str(choice(gifs)['images']['original']['url'])
