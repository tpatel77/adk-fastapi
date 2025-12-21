from __future__ import annotations

import logging
import os
import json
import time
from typing import Any, AsyncGenerator, Optional

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

import litellm


logger = logging.getLogger(__name__)


class X42LiteLLMUsageModel(BaseLlm):
    model: str
    api_base: str
    api_key: str = "not-required"
    extra_headers: dict[str, str] | None = None

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        t0 = time.perf_counter()
        messages: list[dict[str, Any]] = []
        last_tool_call_id_by_name: dict[str, str] = {}
        last_tool_call_id: str | None = None

        def _to_openai_role(role: str) -> str:
            if role == "model":
                return "assistant"
            if role == "assistant":
                return "assistant"
            return role

        system_instruction = getattr(llm_request.config, "system_instruction", None) if llm_request.config else None
        if isinstance(system_instruction, str) and system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        for content in llm_request.contents:
            role = _to_openai_role(content.role or "user")
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            tool_responses: list[types.FunctionResponse] = []

            for part in content.parts or []:
                if not part:
                    continue
                if part.text:
                    text_parts.append(part.text)
                if part.function_call:
                    fc = part.function_call
                    if fc.name:
                        call_id = fc.id or f"call_{len(tool_calls)}"
                        last_tool_call_id_by_name[fc.name] = call_id
                        last_tool_call_id = call_id
                        tool_calls.append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": fc.name,
                                    "arguments": json.dumps(fc.args or {}),
                                },
                            }
                        )
                if part.function_response:
                    tool_responses.append(part.function_response)

            if tool_calls:
                assistant_content: Any = "".join(text_parts) if text_parts else None
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": tool_calls,
                    }
                )
            elif text_parts:
                messages.append({"role": role, "content": "".join(text_parts)})

            for fr in tool_responses:
                tool_msg: dict[str, Any] = {
                    "role": "tool",
                    "content": json.dumps(fr.response or {}),
                }
                if fr.name:
                    tool_msg["name"] = fr.name
                tool_call_id = fr.id
                if not tool_call_id and fr.name:
                    tool_call_id = last_tool_call_id_by_name.get(fr.name)
                if not tool_call_id:
                    tool_call_id = last_tool_call_id
                if tool_call_id:
                    tool_msg["tool_call_id"] = tool_call_id
                messages.append(tool_msg)

        if not messages:
            messages.append({"role": "user", "content": ""})

        tools_payload = None
        tool = None
        if llm_request.config and llm_request.config.tools:
            for maybe_tool in llm_request.config.tools:
                if isinstance(maybe_tool, types.Tool) and maybe_tool.function_declarations:
                    tool = maybe_tool
                    break

        if tool and tool.function_declarations:
            tools_payload = []
            for decl in tool.function_declarations:
                params = None
                if decl.parameters is not None:
                    if hasattr(decl.parameters, "model_dump"):
                        params = decl.parameters.model_dump(exclude_none=True)
                    elif isinstance(decl.parameters, dict):
                        params = decl.parameters
                tools_payload.append(
                    {
                        "type": "function",
                        "function": {
                            "name": decl.name,
                            "description": decl.description,
                            "parameters": params or {"type": "object", "properties": {}},
                        },
                    }
                )

        t1 = time.perf_counter()

        def _to_dict(obj: Any) -> dict[str, Any]:
            if hasattr(obj, "model_dump"):
                return obj.model_dump(exclude_none=True)
            if isinstance(obj, dict):
                return obj
            return json.loads(str(obj))

        if stream:
            aggregated_text = ""
            last_chunk_dict: dict[str, Any] | None = None
            t2_first_token: float | None = None
            tool_calls_by_index: dict[int, dict[str, Any]] = {}

            try:
                resp_stream = await litellm.acompletion(
                    model=self.model,
                    api_base=self.api_base,
                    api_key=self.api_key,
                    messages=messages,
                    stream=True,
                    stream_options={"include_usage": True},
                    extra_headers=self.extra_headers,
                    tools=tools_payload,
                )
            except Exception as e:
                logger.exception(
                    "LiteLLM streaming request failed: %s (messages=%s tools=%s)",
                    str(e),
                    messages[-3:],
                    bool(tools_payload),
                )
                raise

            async for chunk in resp_stream:
                if t2_first_token is None:
                    t2_first_token = time.perf_counter()
                last_chunk_dict = _to_dict(chunk)

                choice0 = (last_chunk_dict.get("choices") or [{}])[0]
                delta = choice0.get("delta") or {}
                delta_text = delta.get("content")
                if delta_text:
                    aggregated_text += delta_text
                    yield LlmResponse(
                        content=types.Content(
                            role="model", parts=[types.Part.from_text(text=delta_text)]
                        ),
                        partial=True,
                        turn_complete=False,
                        custom_metadata={
                            "timings_ms": {
                                "build_messages": (t1 - t0) * 1000.0,
                                "first_token": ((t2_first_token - t0) * 1000.0) if t2_first_token else None,
                            }
                        },
                        model_version=last_chunk_dict.get("model"),
                    )

                delta_tool_calls = delta.get("tool_calls")
                if isinstance(delta_tool_calls, list):
                    for tc in delta_tool_calls:
                        if not isinstance(tc, dict):
                            continue
                        idx = tc.get("index")
                        if not isinstance(idx, int):
                            idx = 0
                        acc = tool_calls_by_index.setdefault(idx, {"name": None, "arguments": ""})

                        fn = tc.get("function")
                        if isinstance(fn, dict):
                            name = fn.get("name")
                            if isinstance(name, str) and name:
                                acc["name"] = name
                            args_fragment = fn.get("arguments")
                            if isinstance(args_fragment, str) and args_fragment:
                                acc["arguments"] += args_fragment

            t3 = time.perf_counter()
            resp_dict = last_chunk_dict or {}

            usage = resp_dict.get("usage")
            usage_metadata = None
            if isinstance(usage, dict):
                usage_metadata = types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=usage.get("prompt_tokens"),
                    candidates_token_count=usage.get("completion_tokens"),
                    total_token_count=usage.get("total_tokens"),
                    thoughts_token_count=(
                        (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
                        if isinstance(usage.get("completion_tokens_details"), dict)
                        else None
                    ),
                    cached_content_token_count=(
                        (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
                        if isinstance(usage.get("prompt_tokens_details"), dict)
                        else None
                    ),
                )

            finish_reason_raw = (resp_dict.get("choices") or [{}])[0].get("finish_reason")
            finish_reason = types.FinishReason.STOP
            if finish_reason_raw == "length":
                finish_reason = types.FinishReason.MAX_TOKENS

            final_parts: list[types.Part] = []
            if aggregated_text:
                final_parts.append(types.Part.from_text(text=aggregated_text))
            elif tool_calls_by_index:
                for _, tc in sorted(tool_calls_by_index.items(), key=lambda kv: kv[0]):
                    name = tc.get("name")
                    args_raw = tc.get("arguments")
                    args: dict[str, Any] = {}
                    if isinstance(args_raw, str) and args_raw:
                        try:
                            args = json.loads(args_raw)
                        except Exception:
                            args = {"_raw": args_raw}
                    if isinstance(name, str) and name:
                        final_parts.append(types.Part.from_function_call(name=name, args=args))

            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=final_parts,
                ),
                finish_reason=finish_reason,
                usage_metadata=usage_metadata,
                partial=False,
                turn_complete=True,
                custom_metadata={
                    "litellm_usage": usage,
                    "timings_ms": {
                        "build_messages": (t1 - t0) * 1000.0,
                        "litellm_call": (t3 - t1) * 1000.0,
                        "total": (t3 - t0) * 1000.0,
                        "first_token": ((t2_first_token - t0) * 1000.0) if t2_first_token else None,
                    },
                    "litellm_raw": resp_dict if os.environ.get("X42_LITELLM_STORE_RAW") == "true" else None,
                },
                model_version=resp_dict.get("model"),
            )
            return

        try:
            resp = await litellm.acompletion(
                model=self.model,
                api_base=self.api_base,
                api_key=self.api_key,
                messages=messages,
                stream=False,
                extra_headers=self.extra_headers,
                tools=tools_payload,
            )
        except Exception as e:
            logger.exception(
                "LiteLLM request failed: %s (messages=%s tools=%s)",
                str(e),
                messages[-3:],
                bool(tools_payload),
            )
            raise

        t2 = time.perf_counter()

        resp_dict = _to_dict(resp)

        t3 = time.perf_counter()

        usage = resp_dict.get("usage")
        usage_metadata = None
        if isinstance(usage, dict):
            usage_metadata = types.GenerateContentResponseUsageMetadata(
                prompt_token_count=usage.get("prompt_tokens"),
                candidates_token_count=usage.get("completion_tokens"),
                total_token_count=usage.get("total_tokens"),
                thoughts_token_count=(
                    (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
                    if isinstance(usage.get("completion_tokens_details"), dict)
                    else None
                ),
                cached_content_token_count=(
                    (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
                    if isinstance(usage.get("prompt_tokens_details"), dict)
                    else None
                ),
            )

        assistant_message = ((resp_dict.get("choices") or [{}])[0].get("message") or {})
        content_text = assistant_message.get("content") or ""

        parts: list[types.Part] = []
        tool_calls = assistant_message.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                fn = (tc.get("function") or {})
                name = fn.get("name")
                args_raw = fn.get("arguments")
                args = None
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {"_raw": args_raw}
                elif isinstance(args_raw, dict):
                    args = args_raw
                if name:
                    parts.append(types.Part.from_function_call(name=name, args=args or {}))
        else:
            parts.append(types.Part.from_text(text=content_text))

        finish_reason_raw = (resp_dict.get("choices") or [{}])[0].get("finish_reason")
        finish_reason = types.FinishReason.STOP
        if finish_reason_raw == "length":
            finish_reason = types.FinishReason.MAX_TOKENS

        llm_response = LlmResponse(
            content=types.Content(role="model", parts=parts),
            finish_reason=finish_reason,
            usage_metadata=usage_metadata,
            custom_metadata={
                "litellm_usage": usage,
                "timings_ms": {
                    "build_messages": (t1 - t0) * 1000.0,
                    "litellm_call": (t2 - t1) * 1000.0,
                    "parse_response": (t3 - t2) * 1000.0,
                    "total": (t3 - t0) * 1000.0,
                },
                "litellm_raw": resp_dict if os.environ.get("X42_LITELLM_STORE_RAW") == "true" else None,
            },
            model_version=resp_dict.get("model"),
        )

        yield llm_response
