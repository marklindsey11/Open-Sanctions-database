import click
import logging
import structlog
from nomenklatura.tui import DedupeApp

from opensanctions.core import Dataset, Context, setup
from opensanctions.exporters import export_global_index, export_dataset
from opensanctions.exporters.common import write_object
from opensanctions.core.http import cleanup_cache
from opensanctions.core.index import get_index, get_index_path
from opensanctions.core.loader import Database
from opensanctions.core.resolver import get_resolver, xref_datasets
from opensanctions.model.statement import Statement
from opensanctions.model.base import migrate_db

log = structlog.get_logger(__name__)
datasets = click.Choice(Dataset.names())


@click.group(help="OpenSanctions ETL toolkit")
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("-q", "--quiet", is_flag=True, default=False)
def cli(verbose=False, quiet=False):
    level = logging.INFO
    if quiet:
        level = logging.WARNING
    if verbose:
        level = logging.DEBUG
    setup(log_level=level)


@cli.command("dump", help="Export the entities from a dataset")
@click.argument("dataset", default=Dataset.ALL, type=datasets)
@click.option("-o", "--outfile", type=click.File("w"), default="-")
def dump_dataset(dataset, outfile):
    dataset = Dataset.get(dataset)
    resolver = get_resolver()
    loader = Database(dataset, resolver).view(dataset)
    for entity in loader:
        write_object(outfile, entity)


@cli.command("crawl", help="Crawl entities into the given dataset")
@click.argument("dataset", default=Dataset.ALL, type=datasets)
def crawl(dataset):
    dataset = Dataset.get(dataset)
    for source in dataset.sources:
        Context(source).crawl()


@cli.command("export", help="Export entities from the given dataset")
@click.argument("dataset", default=Dataset.ALL, type=datasets)
def export(dataset):
    dataset = Dataset.get(dataset)
    resolver = get_resolver()
    Statement.resolve_all(resolver)
    for dataset_ in dataset.datasets:
        export_dataset(dataset_)
    export_global_index()


@cli.command("run", help="Run the full process for the given dataset")
@click.argument("dataset", default=Dataset.ALL, type=datasets)
def run(dataset):
    dataset = Dataset.get(dataset)
    resolver = get_resolver()
    for source in dataset.sources:
        Context(source).crawl()
    Statement.resolve_all(resolver)
    for dataset_ in dataset.datasets:
        export_dataset(dataset_)
    export_global_index()


@cli.command("clear", help="Delete all stored data for the given source")
@click.argument("dataset", default=Dataset.ALL, type=datasets)
def clear(dataset):
    dataset = Dataset.get(dataset)
    for source in dataset.sources:
        Context(source).clear()


@cli.command("resolve", help="Apply de-duplication to the statements table")
def resolve():
    resolver = get_resolver()
    Statement.resolve_all(resolver)


@cli.command("index", help="Index entities from the given dataset")
@click.argument("dataset", default=Dataset.DEFAULT, type=datasets)
def index(dataset):
    resolver = get_resolver()
    Statement.resolve_all(resolver)
    dataset = Dataset.get(dataset)
    loader = Database(dataset, resolver, cached=True).view(dataset)
    path = get_index_path(dataset)
    path.unlink(missing_ok=True)
    get_index(dataset, loader)


@cli.command("xref", help="Generate dedupe candidates from the given dataset")
@click.argument("candidates", type=datasets)
@click.option("-b", "--base", type=datasets, default=Dataset.DEFAULT)
@click.option("-l", "--limit", type=int, default=15)
def xref(base, candidates, limit=15):
    base_dataset = Dataset.get(base)
    candidates_dataset = Dataset.get(candidates)
    xref_datasets(base_dataset, candidates_dataset, limit=limit)


@cli.command("xref-prune", help="Remove dedupe candidates")
@click.option("-k", "--keep", type=int, default=0)
def xref_prune(keep=0):
    resolver = get_resolver()
    resolver.prune(keep=keep)
    resolver.save()


@cli.command("dedupe", help="Interactively judge xref candidates")
@click.option("-d", "--dataset", type=datasets, default=Dataset.DEFAULT)
def dedupe(dataset):
    resolver = get_resolver()
    dataset = Dataset.get(dataset)
    db = Database(dataset, resolver)
    DedupeApp.run(
        title="OpenSanction De-duplication",
        # log="textual.log",
        loader=db.view(dataset),
        resolver=resolver,
    )


@cli.command("explode", help="Destroy a cluster of deduplication matches")
@click.argument("canonical_id", type=str)
def explode(canonical_id):
    resolver = get_resolver()
    resolved_id = resolver.get_canonical(canonical_id)
    resolver.explode(resolved_id)
    resolver.save()
    Statement.resolve_all(resolver)


@cli.command("prof", help="Profile test")
@click.option("-d", "--dataset", type=datasets, default=Dataset.DEFAULT)
def prof(dataset):
    resolver = get_resolver()
    dataset = Dataset.get(dataset)

    import time
    import gc
    from nomenklatura.index import Index

    db = Database(dataset, resolver, cached=True)
    loader = db.view(dataset)
    gc.collect()
    while True:
        time.sleep(1)
    return
    index = Index(loader)
    index.build(fuzzy=False)
    index.save("sanctions.pkl")
    resolver.prune()

    # for pair, score in index.pairs()[:10000]:
    #     left, right = pair
    #     left_entity = loader.get_entity(left)
    #     right_entity = loader.get_entity(right)
    #     if left_entity is None or right_entity is None:
    #         continue
    #     if left_entity.schema not in right_entity.schema.matchable_schemata:
    #         continue
    #     if not resolver.check_candidate(left, right):
    #         continue
    #     resolver.suggest(left, right, score)
    #     # print(pair, score)
    resolver.save()


@cli.command("cleanup", help="Clean up caches")
def cleanup():
    cleanup_cache()


@cli.command("migrate", help="Create a new database autogenerated migration")
@click.option("-m", "--message", "message")
def migrate(message):
    migrate_db(message)


if __name__ == "__main__":
    cli()
