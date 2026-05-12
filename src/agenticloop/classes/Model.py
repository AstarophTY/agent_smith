import asyncio
import os
import time
from typing import List, Optional

from dotenv import load_dotenv
import httpx
from openai import (
    AsyncOpenAI,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
)
from openai.types.chat import ChatCompletionMessageParam

from agenticloop.classes.LLMResponse import LLMResponse
from logger.classes.Logger import Logger


class Model:
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        load_dotenv()
        self.base_url: str = (
            base_url
            or os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
            or ""
        )
        self.model_name: str = (
            model_name
            or os.getenv("LLM_MODEL", "google/gemini-2.0-flash-001")
            or ""
        )
        self._api_keys = self._load_api_keys()
        self._key_index = 0
        self.client = self._make_client()

    def _load_api_keys(self) -> list[str]:
        """Load API keys (LLM_API_KEY, LLM_API_KEY_1, LLM_API_KEY_2...)."""
        keys: list[str] = []
        primary = os.getenv("LLM_API_KEY", "")
        if primary:
            keys.append(primary)
        i = 1
        while True:
            k = os.getenv(f"LLM_API_KEY_{i}", "")
            if not k:
                break
            keys.append(k)
            i += 1
        return keys or ["no-key"]

    def _make_client(self) -> AsyncOpenAI:
        key = self._api_keys[self._key_index % len(self._api_keys)]
        return AsyncOpenAI(
            api_key=key,
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=30.0,
                read=180.0,
                write=30.0,
                pool=30.0,
            ),
        )

    def _rotate_key(self) -> None:
        self._key_index += 1
        self.client = self._make_client()
        Logger.warning(
            f"Rotated to API key index {self._key_index % len(self._api_keys)}"
        )

    async def get_next_step(
        self,
        prompt: str,
        history: Optional[List[ChatCompletionMessageParam]] = None,
        system_prompt: str = "",
        max_retries: int = 5,
    ) -> LLMResponse:
        messages: List[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        retries = 0
        last_error: Optional[Exception] = None

        while retries <= max_retries:
            start_time = time.time()
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=0.2,
                        stop=["<end_code>", "\nObservation:"],
                    ),
                    timeout=180.0,
                )
                elapsed_ms = (time.time() - start_time) * 1000
                full_text = response.choices[0].message.content or ""
                input_tokens = 0
                output_tokens = 0
                if response.usage:
                    input_tokens = response.usage.prompt_tokens or 0
                    output_tokens = response.usage.completion_tokens or 0

                Logger.debug(
                    f"LLM response (in={input_tokens} out={output_tokens} "
                    f"ms={elapsed_ms:.0f}): {full_text[:300]}"
                )
                result = self._parse_output(full_text)
                result.input_tokens = input_tokens
                result.output_tokens = output_tokens
                result.retries = retries
                result.request_time_ms = elapsed_ms
                return result

            except RateLimitError as e:
                last_error = e
                retries += 1
                if len(self._api_keys) > 1:
                    self._rotate_key()
                    wait_time = 5
                else:
                    wait_time = min(60 * retries, 300)
                Logger.warning(
                    f"Rate limit (attempt {retries}/{max_retries}): {e}. "
                    f"Waiting {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except (APITimeoutError, asyncio.TimeoutError) as e:
                last_error = e
                retries += 1
                wait_time = min(15 * retries, 90)
                Logger.warning(
                    f"Timeout (attempt {retries}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except APIConnectionError as e:
                last_error = e
                retries += 1
                wait_time = min(10 * retries, 60)
                Logger.warning(
                    f"Connection error (attempt {retries}/{max_retries}): {e} "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                last_error = e
                retries += 1
                wait_time = min(2**retries, 60)
                Logger.warning(
                    f"LLM call failed (attempt {retries}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

        raise last_error  # type: ignore[misc]

    def _parse_output(self, text: str) -> LLMResponse:
        import re

        code_match = re.search(r"```python\s+(.*?)\s*```", text, re.DOTALL)
        if not code_match:
            code_match = re.search(r"```\s+(.*?)\s*```", text, re.DOTALL)

        if code_match:
            Logger.debug("Found code block in LLM response")
            code = code_match.group(1).strip()
            thought = text.replace(code_match.group(0), "").strip()
        else:
            Logger.debug("No code block found in LLM response")
            code = None
            thought = text.strip()

        return LLMResponse(thought=thought, code=code, raw_content=text)
