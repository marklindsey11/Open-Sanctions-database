import csv
from typing import Dict
from pantomime.types import CSV

from opensanctions.core import Context
from opensanctions import helpers as h
from opensanctions.util import multi_split

TYPES = {
    "Person": "Person",
    "Organization": "Organization",
    "": "LegalEntity",
}


def parse_date(date):
    return h.parse_date(date, ["%d.%m.%Y"])


def crawl_row(context: Context, row: Dict[str, str]):
    entity = context.make(TYPES[row.pop("Entity_Type")])
    row.pop("Entity_Type_BG")
    entity.id = context.make_id(
        row.get("Label"),
        row.get("First_Name"),
        row.get("First_Name_BG"),
        row.get("Second_Name"),
        row.get("Second_Name_BG"),
        row.get("Family_Name"),
        row.get("Family_Name_BG"),
        row.get("DOB"),
        row.get("Place_of_birth"),
        row.get("Place_of_birth_BG"),
    )
    if entity.id is None:
        return

    h.apply_name(
        entity,
        first_name=row.pop("First_Name"),
        second_name=row.pop("Second_Name"),
        last_name=row.pop("Family_Name"),
        quiet=True,
    )
    h.apply_name(
        entity,
        first_name=row.pop("First_Name_BG"),
        second_name=row.pop("Second_Name_BG"),
        last_name=row.pop("Family_Name_BG"),
        alias=True,
        quiet=True,
    )

    entity.add("alias", row.pop("Aliases", "").split(";"))
    entity.add("alias", row.pop("Aliases_BG", "").split(";"))
    entity.add("country", row.pop("Countries_of_Residence", "").split(";"))
    entity.add("country", row.pop("Countries_of_Residence_BG", "").split(";"))
    if entity.schema.is_a("Person"):
        entity.add("nationality", row.pop("Citizenships"))
        entity.add("nationality", row.pop("Citizenships_BG"))
    else:
        entity.add("jurisdiction", row.pop("Citizenships"))
        entity.add("jurisdiction", row.pop("Citizenships_BG"))
    entity.add("birthPlace", row.pop("Place_of_birth"), quiet=True)
    entity.add("birthPlace", row.pop("Place_of_birth_BG"), quiet=True)
    for part in multi_split([row.pop("DOB"), row.pop("DOB_BG")], [";", "/"]):
        entity.add("birthDate", parse_date(part), quiet=True)
    entity.add("passportNumber", row.pop("Passport_No"), quiet=True)
    entity.add("passportNumber", row.pop("Passport_No_BG"), quiet=True)
    entity.add("idNumber", row.pop("National_ID"), quiet=True)
    entity.add("idNumber", row.pop("National_ID_BG"), quiet=True)
    # entity.add("taxNumber", row.pop("Italian_Fiscal_Code"), quiet=True)
    entity.add("taxNumber", row.pop("Italian_Fiscal_Code_BG"), quiet=True)
    entity.add("position", row.pop("Position"), quiet=True)
    entity.add("position", row.pop("Position_BG"), quiet=True)
    entity.add("sourceUrl", row.pop("Source_URL"))
    entity.add("sourceUrl", row.pop("Source_URL_BG"))
    entity.add("notes", row.pop("Notes"))
    entity.add("notes", row.pop("Notes_BG"))
    entity.add("address", row.pop("Addresses"))
    entity.add("address", row.pop("Addresses_BG"))
    # context.inspect(row)
    context.emit(entity, target=True)


def crawl(context: Context):
    path = context.fetch_resource("source.csv", context.dataset.data.url)
    context.export_resource(path, CSV, title=context.SOURCE_TITLE)
    with open(path, "r") as fh:
        for row in csv.DictReader(fh):
            crawl_row(context, row)