from functools import wraps
from platform import python_version
from typing import Any, Callable, Generic, Optional, TypeVar, Union

from pydantic.generics import GenericModel

if python_version().startswith("3.7"):
    from typing_extensions import get_origin, get_type_hints
else:
    from typing import get_origin, get_type_hints

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from returns.pipeline import is_successful
from returns.result import Result


class ErrorDetails(BaseModel):
    message: str


class NotSetSentinel:
    ...


NOT_SET = NotSetSentinel()


DetailType = Optional[Union[BaseModel, str]]


class ApiError(Exception):
    status_code: int
    detail: DetailType = None

    def __init__(self, detail: Union[DetailType, NotSetSentinel] = NOT_SET) -> None:
        if detail is not NOT_SET:
            assert not isinstance(detail, NotSetSentinel)
            self.detail = detail


T = TypeVar("T")


class ApiErrorSchema(GenericModel, Generic[T]):
    detail: T


EndpointResultType = Result[BaseModel, ApiError]
EndpointType = Callable[..., EndpointResultType]


class ResultRouter(APIRouter):
    def add_api_route(
        self,
        path: str,
        endpoint: Callable[..., Any],
        **kwargs: Any,
    ) -> None:
        return_type = get_type_hints(endpoint)["return"]

        success_result, failure_result = return_type.__args__

        endpoint = self._unpacked_container(endpoint)

        responses = {}
        if get_origin(failure_result) is Union:
            for error in failure_result.__args__:
                annotation = error.__annotations__["detail"]
                responses[error.status_code] = {"model": ApiErrorSchema[annotation]}  # type: ignore[valid-type]
        else:
            annotation = failure_result.__annotations__["detail"]
            responses[failure_result.status_code] = {"model": ApiErrorSchema[annotation]}  # type: ignore[valid-type]

        if kwargs["response_model"] is None:
            kwargs["response_model"] = success_result

        if kwargs["responses"] is None:
            kwargs["responses"] = responses

        return super().add_api_route(path, endpoint, **kwargs)

    @staticmethod
    def _unpacked_container(endpoint_func: EndpointType) -> Callable[..., BaseModel]:
        @wraps(endpoint_func)
        def decorator(*args: Any, **kwargs: Any) -> BaseModel:
            result = endpoint_func(*args, **kwargs)

            if is_successful(result):
                return result.unwrap()
            else:
                exception: ApiError = result.failure()

                raise HTTPException(status_code=exception.status_code, detail=exception.detail)

        return decorator
