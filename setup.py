from setuptools import setup, find_packages

setup(
    name="codemind",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
        "tree-sitter",
        "tree-sitter-languages",
        "networkx",
        "chromadb",
        "sentence-transformers",
        "openai",
        "python-dotenv",
        "pydantic",
    ],
    entry_points={
        'console_scripts': [
            'codemind=codemind.cli:cli',
        ],
    },
)
