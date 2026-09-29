from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from examples.fastapi_app.container import build_provider
from examples.fastapi_app.services import ReportService
from pydico import ServiceScope


class CreateReportBody(BaseModel):
    title: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    provider = build_provider()
    app.state.service_provider = provider
    try:
        yield
    finally:
        await provider.aclose()


app = FastAPI(title="pydico FastAPI example", lifespan=lifespan)


def request_scope(request: Request) -> Iterator[ServiceScope]:
    provider = request.app.state.service_provider
    with provider.create_scope() as scope:
        yield scope


def report_service(
    scope: Annotated[ServiceScope, Depends(request_scope)],
) -> ReportService:
    service = scope.get_service(ReportService)
    if service is None:
        raise RuntimeError("ReportService is not registered.")
    return service


ReportServiceDependency = Annotated[ReportService, Depends(report_service)]


@app.post("/reports", status_code=201)
def create_report(body: CreateReportBody, service: ReportServiceDependency):
    try:
        return service.create(body.title)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/reports")
def list_reports(service: ReportServiceDependency):
    return service.list()
