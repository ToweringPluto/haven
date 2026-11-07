"""Shared bits for the dataset loaders."""

OGL_GOV_SCOT = (
    "Crown copyright, Scottish Government. Open Government Licence v3.0 "
    "(https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)."
)


class LoaderSourceMissing(Exception):
    """The loader's local source (e.g. a raw download) isn't present."""


def monthly_from_weekly(weekly_gbp: float) -> float:
    """Monthly equivalent of a weekly amount: weekly * 52 / 12, rounded to the penny."""
    return round(weekly_gbp * 52 / 12, 2)
