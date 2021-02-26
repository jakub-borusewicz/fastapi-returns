from __future__ import annotations

from functools import wraps

from fastapi.routing import APIRoute
from pydantic import BaseModel
from returns.pipeline import is_successful
from returns.result import Result, Success
from typing import Callable, Any, get_type_hints, Sequence

from fastapi import APIRouter, HTTPException



class ApiError(Exception):
    status_code: int
    details: str
    # def __hash__(self):


class ErrorHandlingRoute(APIRoute):
    ...


def unpack_container(endpoint_func) -> Callable:
    @wraps(endpoint_func)
    def decorator(*args, **kwargs):
        result: Result = endpoint_func(*args, **kwargs)

        if is_successful(result):
            return result.unwrap()
        else:
            exception: ApiError = result.failure()

            raise HTTPException(status_code=exception.status_code, detail=exception.details)

    return decorator


class ErrorHandlingRouter(APIRouter):
    """
    Overrides the route decorator logic to use the annotated return type as the `response_model` if unspecified.
    """

    # if not TYPE_CHECKING:  # pragma: no branch

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._errors_mapping = {}

    def add_api_route(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        if kwargs.get("response_model") is None:
            result_type = get_type_hints(endpoint).get("return")
            # assert result_type in (Result.success_type, Result.failure_type)

            success_result: Result
            success_result, failure_result = result_type.__args__

            resulta: ApiError
            resultb: ApiError

            resulta, resultb = failure_result.__args__

            kwargs["response_model"] = success_result
            kwargs["responses"] = {
                # resulta.status_code: {"model": ErrorDetails},
                # resultb.status_code: {"model": ErrorDetails},
                resulta.status_code: {"model": type(resulta.details)},
                resultb.status_code: {"model": type(resultb.details)},
            }

            endpoint = unpack_container(endpoint)
        return super().add_api_route(path, endpoint, route_class_override=ErrorHandlingRoute, **kwargs)
