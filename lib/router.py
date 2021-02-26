from __future__ import annotations

from fastapi.datastructures import DefaultPlaceholder, Default
from fastapi.openapi.models import Response
from functools import wraps
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute
from types import GenericAlias
from typing import Any, Callable, Dict, get_origin, get_type_hints, Optional, Type, List, Sequence, Union, Set

from fastapi import APIRouter, HTTPException, params
from fastapi.encoders import jsonable_encoder, SetIntStr, DictIntStrAny
from fastapi.routing import APIRoute
from pydantic import BaseModel
from returns.pipeline import is_successful
from returns.result import Result


class ErrorDetails(BaseModel):
    message: str


class ApiError(Exception):
    status_code: int
    details: ErrorDetails


class ErrorHandlingRoute(APIRoute):
    ...


EndpointResultType = Result[BaseModel, ApiError]
EndpointType = Callable[..., EndpointResultType]


class ErrorHandlingRouter(APIRouter):
    """
    Overrides the route decorator logic to use the annotated return type as the `response_model` if unspecified.
    """

    def add_api_route(
            self,
            path: str,
            endpoint: Callable[..., Any],
            **kwargs,
    ) -> None:
        return_type = get_type_hints(endpoint)["return"]
        assert get_origin(return_type) is Result, "Endpoint return type must be returns.Result"
        success_result: BaseModel
        success_result, failure_result = return_type.__args__

        response_model = success_result

        responses = {}
        for exception in failure_result.__args__:
            responses[exception.status_code] = {"model": type(exception.details)}

        endpoint = self._unpacked_container(endpoint)
        route_class_override = ErrorHandlingRoute
        return super().add_api_route(
            path,
            endpoint, response_model=response_model, responses=responses, **kwargs
        )

    @staticmethod
    def _unpacked_container(endpoint_func: EndpointType) -> Callable[..., BaseModel]:
        @wraps(endpoint_func)
        def decorator(*args: Any, **kwargs: Any) -> BaseModel:
            result = endpoint_func(*args, **kwargs)

            if is_successful(result):
                return result.unwrap()
            else:
                exception: ApiError = result.failure()

                raise HTTPException(status_code=exception.status_code, detail=jsonable_encoder(exception.details))

        return decorator
