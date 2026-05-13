import click
import os
import glob
import logging
from pathlib import Path
from dotenv import load_dotenv
from codemind.extractor import CodeExtractor
from codemind.graph_builder import GraphBuilder
from codemind.retriever import CodeRetriever
from codemind.agent import CodeAgent
from codemind.reporter import Reporter
from codemind.utils import setup_logging, FileCache

DEFAULT_DB = "./codemind_data"

@click.group()
def cli():
    """CodeMind: AI-powered codebase analysis tool."""
    load_dotenv() # Load variables from .env if it exists
    setup_logging()
    pass

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--db', 'db_path', default=DEFAULT_DB, help='Path to store indices.')
def build(path, db_path):
    """Build knowledge graph and vector index from source code."""
    os.makedirs(db_path, exist_ok=True)
    cache = FileCache(os.path.join(db_path, "parse_cache.json"))
    
    extractor = CodeExtractor()
    graph_builder = GraphBuilder()
    
    # Load existing graph if it exists to update
    graph_file = os.path.join(db_path, "graph.json")
    if os.path.exists(graph_file):
        graph_builder.load_graph(graph_file)

    retriever = CodeRetriever(db_path=os.path.join(db_path, "chroma"))
    
    click.echo(f"Scanning {path} for Python files...")
    py_files = glob.glob(os.path.join(path, "**/*.py"), recursive=True)
    
    all_parsed = {}
    with click.progressbar(py_files, label="Analyzing files") as bar:
        for f in bar:
            if cache.is_changed(f):
                parsed = extractor.parse_file(f)
                all_parsed[f] = parsed
                graph_builder.build_graph(parsed, file_path=f)
                cache.update(f)

    if all_parsed:
        click.echo(f"Indexing {len(all_parsed)} updated snippets...")
        retriever.index_codebase(all_parsed, path)
        graph_builder.save_graph(graph_file)
        cache.save()
        click.echo("Build complete.")
    else:
        click.echo("No changes detected. Index is up to date.")

@cli.command()
@click.argument('query')
@click.option('--db', 'db_path', default=DEFAULT_DB, help='Path to indices.')
def ask(query, db_path):
    """Ask questions about the codebase."""
    graph_builder = GraphBuilder()
    graph_builder.load_graph(os.path.join(db_path, "graph.json"))
    retriever = CodeRetriever(db_path=os.path.join(db_path, "chroma"))
    
    agent = CodeAgent(graph_builder, retriever)
    answer = agent.run(query)
    
    click.echo("\n--- FINAL ANSWER ---")
    click.echo(answer)

@cli.command()
@click.option('--db', 'db_path', default=DEFAULT_DB, help='Path to indices.')
@click.option('--output', '-o', help='Path to save report.')
@click.option('--format', type=click.Choice(['markdown', 'html']), default='markdown')
def report(db_path, output, format):
    """Generate risk report."""
    graph_builder = GraphBuilder()
    graph_builder.load_graph(os.path.join(db_path, "graph.json"))
    reporter = Reporter(graph_builder)
    
    if output:
        reporter.save_report(output, format=format)
        click.echo(f"Report saved to {output}")
    else:
        click.echo(reporter.generate_markdown())

if __name__ == "__main__":
    cli()
