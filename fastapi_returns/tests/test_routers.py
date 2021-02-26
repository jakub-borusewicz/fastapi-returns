import datetime
from platform import python_version
from typing import Union

if python_version().startswith("3.7"):
    from typing_extensions import Literal
else:
    from typing import Literal  # type: ignore[misc]

from fastapi import FastAPI
from pydantic import BaseModel
from returns.result import Failure, Result, Success
from starlette import status
from starlette.testclient import TestClient

from fastapi_returns._routers import ApiError, ResultRouter


class TestApiError:
    def test_detail_is_none_if_message_is_unspecified(self) -> None:
        # given
        class DummyApiError(ApiError):
            status_code = 404

        # when
        error = DummyApiError()

        # then
        assert error.detail is None


class TestResultRouter:
    def test_success_response(self) -> None:
        # given
        router = ResultRouter()

        class DummyModel(BaseModel):
            some_field: str

        class DummyApiError(ApiError):
            status_code = 400
            detail = "dummy message"

        @router.get("/dummy_view")
        def dummy_view() -> Result[DummyModel, DummyApiError]:
            return Success(DummyModel(some_field="some value"))

        app = FastAPI()
        app.include_router(router)
        api_client = TestClient(app)

        # when
        response = api_client.get("/dummy_view")

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"some_field": "some value"}

    def test_failure_response(self) -> None:
        # given
        router = ResultRouter()

        class DummyModel(BaseModel):
            some_field: str

        class DummyApiError(ApiError):
            status_code = 400
            detail = "dummy message"

        @router.get("/dummy_view")
        def dummy_view() -> Result[DummyModel, DummyApiError]:
            return Failure(DummyApiError())

        app = FastAPI()
        app.include_router(router)
        api_client = TestClient(app)

        # when
        response = api_client.get("/dummy_view")

        # then
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "dummy message"}


class TestResultRouterSchemaResponses:
    def test_schema_response(self) -> None:
        # given
        router = ResultRouter()

        class DummyModel(BaseModel):
            some_field: str

        class DummyErrorDetailsModel(BaseModel):
            error_datetime: datetime.datetime

        class DummyApiStringAnnotationError(ApiError):
            status_code = 404
            detail: str = "dummy not found message"

        class DummyApiLiteralError(ApiError):
            status_code = 403
            detail: Literal["dummy forbidden message"] = "dummy forbidden message"

        class DummyApiPydanticError(ApiError):
            status_code = 403
            detail: DummyErrorDetailsModel

        @router.get("/dummy_view")
        def dummy_view() -> Result[
            DummyModel, Union[DummyApiStringAnnotationError, DummyApiLiteralError, DummyApiPydanticError]
        ]:
            ...

        app = FastAPI()
        app.include_router(router)
        api_client = TestClient(app)

        # when
        response = api_client.get("/openapi.json")

        # then
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "components": {
                "schemas": {
                    "ApiErrorSchema_DummyErrorDetailsModel_": {
                        "properties": {"detail": {"$ref": "#/components/schemas/DummyErrorDetailsModel"}},
                        "required": ["detail"],
                        "title": "ApiErrorSchema[DummyErrorDetailsModel]",
                        "type": "object",
                    },
                    "ApiErrorSchema_str_": {
                        "properties": {"detail": {"title": "Detail", "type": "string"}},
                        "required": ["detail"],
                        "title": "ApiErrorSchema[str]",
                        "type": "object",
                    },
                    "DummyErrorDetailsModel": {
                        "properties": {
                            "error_datetime": {"format": "date-time", "title": "Error " "Datetime", "type": "string"}
                        },
                        "required": ["error_datetime"],
                        "title": "DummyErrorDetailsModel",
                        "type": "object",
                    },
                    "DummyModel": {
                        "properties": {"some_field": {"title": "Some " "Field", "type": "string"}},
                        "required": ["some_field"],
                        "title": "DummyModel",
                        "type": "object",
                    },
                }
            },
            "info": {"title": "FastAPI", "version": "0.1.0"},
            "openapi": "3.0.2",
            "paths": {
                "/dummy_view": {
                    "get": {
                        "operationId": "dummy_view_dummy_view_get",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "#/components/schemas/DummyModel"}}
                                },
                                "description": "Successful " "Response",
                            },
                            "403": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ApiErrorSchema_DummyErrorDetailsModel_"
                                        }
                                    }
                                },
                                "description": "Forbidden",
                            },
                            "404": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "#/components/schemas/ApiErrorSchema_str_"}}
                                },
                                "description": "Not " "Found",
                            },
                        },
                        "summary": "Dummy View",
                    }
                }
            },
        }
