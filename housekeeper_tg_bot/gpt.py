import requests
from loguru import logger
from requests.exceptions import ReadTimeout
from urllib3.exceptions import ReadTimeoutError

SUCCESS_CODE = 200


def get_gpt_response(prompt: str) -> str | None:
    # Gets a response from GPT-3 at https://pelevin.gpt.dobro.ai/generate/

    request_body = {'prompt': prompt, 'length': 39}
    try:
        response = requests.post(
            'https://pelevin.gpt.dobro.ai/generate/',
            json=request_body,
            timeout=5,
        )
    except (ReadTimeout, ReadTimeoutError, TimeoutError) as e:
        logger.error('GPT-3 request timeout: {}', e)
        return None

    if response.status_code != SUCCESS_CODE:
        logger.error('GPT-3 request failed: {}', response.text)
        return None
    return str(response.json()['replies'][0])
