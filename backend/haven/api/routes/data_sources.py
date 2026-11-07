"""The dataset registry, for the "Data and limits" page."""

from fastapi import APIRouter, Request

from haven.api import examples as ex
from haven.api.schemas import DataSource, DataSourceList
from haven.datasets import Registry, load_registry

router = APIRouter(tags=["meta"])


def to_list(registry: Registry) -> DataSourceList:
    return DataSourceList(
        items=[
            DataSource(
                id=d.id,
                name=d.name,
                url=d.url,
                licence_note=d.licence_note,
                as_of=d.as_of,
                caveats=list(d.caveats),
            )
            for d in registry.datasets
        ]
    )


@router.get(
    "/data-sources",
    response_model=DataSourceList,
    summary="Datasets Haven uses, with licence, date and known limits",
    description="Every dataset from the registry (`data/datasets.yml`), in registry order. "
    "Show `licence_note` and every caveat verbatim, and link `url`.",
    responses=ex.json_response(
        200, ex.single(to_list(load_registry()).model_dump(mode="json"), "The registry")
    ),
)
def get_data_sources(request: Request) -> DataSourceList:
    registry: Registry = request.app.state.registry
    return to_list(registry)
